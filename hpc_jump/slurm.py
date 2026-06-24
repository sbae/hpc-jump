from __future__ import annotations

import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .config import ClusterConfig

DEFAULT_SSH_TIMEOUT_SECONDS = 60
DEFAULT_ALLOCATION_TIMEOUT_SECONDS = 3600
_SSH_VERBOSE = False
_OUTPUT_START = "__HPC_JUMP_OUTPUT_START__"
_OUTPUT_END = "__HPC_JUMP_OUTPUT_END__"


@dataclass(frozen=True)
class SlurmJob:
    job_id: str
    state: str
    node: str | None = None
    name: str | None = None


def _ssh_target(cluster: ClusterConfig) -> str:
    if cluster.user:
        return f"{cluster.user}@{cluster.login_host}"
    return cluster.login_host


def _ssh_args(cluster: ClusterConfig) -> list[str]:
    args = ["ssh", "-p", str(cluster.port)]
    if _SSH_VERBOSE:
        args.append("-v")
    if cluster.identity_file:
        args.extend(["-i", str(Path(cluster.identity_file).expanduser())])
    return args


def set_ssh_verbose(enabled: bool) -> None:
    global _SSH_VERBOSE
    _SSH_VERBOSE = enabled


def run_login(
    cluster: ClusterConfig,
    command: str,
    check: bool = True,
    timeout: int = DEFAULT_SSH_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    # SSH runs commands in a non-login shell, which commonly has a reduced PATH
    # on HPC systems. Use a login shell so site Slurm setup is loaded. Sites that
    # require an environment module can provide remote_init in the cluster config.
    init = f"{cluster.remote_init} || exit $?; " if cluster.remote_init else ""
    framed_command = (
        f"{init}printf '{_OUTPUT_START}\\n'; "
        f"{command}; status=$?; "
        f"printf '\\n{_OUTPUT_END}\\n'; exit $status"
    )
    remote_command = f"bash -lc {shlex.quote(framed_command)}"
    proc = subprocess.run(
        [
            *_ssh_args(cluster),
            "-o",
            f"ConnectTimeout={min(timeout, DEFAULT_SSH_TIMEOUT_SECONDS)}",
            _ssh_target(cluster),
            remote_command,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )
    if _SSH_VERBOSE and proc.stderr:
        print(proc.stderr, file=sys.stderr, end="" if proc.stderr.endswith("\n") else "\n")

    # Login profiles sometimes print greetings. Only expose output produced by
    # the requested command so those messages cannot corrupt Slurm parsers.
    if _OUTPUT_START in proc.stdout and _OUTPUT_END in proc.stdout:
        stdout = proc.stdout.rsplit(_OUTPUT_START, 1)[1].split(_OUTPUT_END, 1)[0]
        stdout = stdout.removeprefix("\r\n").removeprefix("\n").removesuffix("\r\n").removesuffix("\n")
        proc = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, proc.stderr)
    if check and proc.returncode != 0:
        detail = "" if _SSH_VERBOSE else (proc.stderr.strip() or proc.stdout.strip())
        message = f"Remote SSH command failed with exit code {proc.returncode}."
        if detail:
            message = f"{message}\n{detail}"
        raise RuntimeError(message)
    return proc


def _first_host_from_nodelist(cluster: ClusterConfig, nodelist: str) -> str | None:
    if not nodelist or nodelist in {"(null)", "None", "N/A"}:
        return None
    cmd = f"scontrol show hostnames {shlex.quote(nodelist)} | head -n 1"
    out = run_login(cluster, cmd).stdout.strip()
    return out or None


def resolve_job(cluster: ClusterConfig, job_id: str) -> SlurmJob:
    fmt = "%i|%T|%N|%j"
    cmd = f"squeue -j {shlex.quote(job_id)} -h -o {shlex.quote(fmt)}"
    out = run_login(cluster, cmd).stdout.strip()
    if not out:
        raise RuntimeError(f"No active Slurm job found with id {job_id}")

    line = out.splitlines()[0]
    parts = line.split("|", 3)
    if len(parts) != 4:
        raise RuntimeError(f"Could not parse squeue output: {line}")

    job, state, nodelist, name = parts
    return SlurmJob(job_id=job, state=state, node=_first_host_from_nodelist(cluster, nodelist), name=name)


def find_reusable_job(cluster: ClusterConfig, partition: str | None = None) -> SlurmJob | None:
    fmt = "%i|%T|%P|%N|%j"
    cmd = f"squeue -u $USER -h -t RUNNING -o {shlex.quote(fmt)}"
    out = run_login(cluster, cmd, check=False).stdout.strip()
    if not out:
        return None

    for line in out.splitlines():
        parts = line.split("|", 4)
        if len(parts) != 5:
            continue
        job_id, state, job_partition, nodelist, name = parts
        if name != cluster.job_name_prefix:
            continue
        if partition and job_partition != partition:
            continue
        node = _first_host_from_nodelist(cluster, nodelist)
        if node:
            return SlurmJob(job_id=job_id, state=state, node=node, name=name)
    return None


def allocate_job(
    cluster: ClusterConfig,
    partition: str | None,
    time_limit: str,
    cpus: int,
    mem: str,
    extra: Sequence[str] | None = None,
    timeout_seconds: int = DEFAULT_ALLOCATION_TIMEOUT_SECONDS,
) -> str:
    args = [
        "salloc",
        "--no-shell",
        f"--job-name={cluster.job_name_prefix}",
        f"--time={time_limit}",
        f"--cpus-per-task={cpus}",
        f"--mem={mem}",
    ]
    if partition:
        args.append(f"--partition={partition}")
    args.extend(extra or [])

    remote_cmd = " ".join(shlex.quote(x) for x in args)
    proc = run_login(cluster, remote_cmd, check=False, timeout=timeout_seconds)
    combined = "\n".join([proc.stdout, proc.stderr])
    match = re.search(r"\b(?:Granted|Pending) job allocation (\d+)\b", combined)
    if match:
        return match.group(1)

    raise RuntimeError(
        "Could not allocate a Slurm job or determine its id. "
        f"remote exit code={proc.returncode}. "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def wait_for_node(cluster: ClusterConfig, job_id: str, poll_seconds: float = 3.0, timeout_seconds: int = 3600) -> SlurmJob:
    deadline = time.time() + timeout_seconds
    last: SlurmJob | None = None
    while time.time() < deadline:
        job = resolve_job(cluster, job_id)
        last = job
        if job.state == "RUNNING" and job.node:
            return job
        if job.state in {"FAILED", "CANCELLED", "TIMEOUT", "COMPLETED"}:
            raise RuntimeError(f"Job {job_id} ended before a node was available: {job.state}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for job {job_id}. Last status: {last}")


def cancel_job(cluster: ClusterConfig, job_id: str) -> None:
    run_login(cluster, f"scancel {shlex.quote(job_id)}")

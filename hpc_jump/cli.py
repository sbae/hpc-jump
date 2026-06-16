from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import DEFAULT_CONFIG_PATH, load_cluster
from .doctor import (
    check_config_file,
    check_executable,
    check_login_reachable,
    check_python,
    check_remote_command,
    check_ssh_config_writable,
    check_vscode_remote_ssh,
    platform_summary,
)
from .slurm import allocate_job, cancel_job, find_reusable_job, resolve_job, wait_for_node
from .ssh_config import DEFAULT_SSH_CONFIG, update_ssh_config
from .vscode import launch_vscode

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def connect(
    cluster_name: str = typer.Argument(..., help="Cluster profile name from config.toml."),
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, "--config", help="Path to config.toml."),
    partition: str | None = typer.Option(None, "--partition", help="Slurm partition."),
    time_limit: str | None = typer.Option(None, "--time", help="Slurm time limit."),
    cpus: int | None = typer.Option(None, "--cpus", help="CPUs per task."),
    mem: str | None = typer.Option(None, "--mem", help="Memory request."),
    existing_job: str | None = typer.Option(None, "--existing-job", help="Attach to an active Slurm job id."),
    no_reuse: bool = typer.Option(False, "--no-reuse", help="Do not auto-reuse an existing running job."),
    no_launch: bool = typer.Option(False, "--no-launch", help="Update SSH config but do not launch VS Code."),
    ssh_config: Path = typer.Option(DEFAULT_SSH_CONFIG, "--ssh-config", help="Path to SSH config."),
    path: str | None = typer.Option(None, "--path", help="Remote path to open in VS Code."),
    wait_timeout: int = typer.Option(3600, "--wait-timeout", help="Seconds to wait for a new allocation."),
) -> None:
    cluster = load_cluster(cluster_name, config)
    part = partition if partition is not None else cluster.default_partition
    tlim = time_limit if time_limit is not None else cluster.default_time
    ncpus = cpus if cpus is not None else cluster.default_cpus
    memory = mem if mem is not None else cluster.default_mem
    remote_path = path if path is not None else cluster.remote_project_path

    if existing_job:
        console.print(f"Attaching to existing Slurm job {existing_job}...")
        job = resolve_job(cluster, existing_job)
        if not job.node:
            job = wait_for_node(cluster, existing_job, timeout_seconds=wait_timeout)
    else:
        job = None
        if cluster.auto_reuse and not no_reuse:
            console.print("Looking for reusable running Slurm job...")
            job = find_reusable_job(cluster, partition=part)

        if job is None:
            console.print("Requesting new Slurm allocation...")
            job_id = allocate_job(
                cluster=cluster,
                partition=part,
                time_limit=tlim,
                cpus=ncpus,
                mem=memory,
                extra=cluster.salloc_extra,
            )
            console.print(f"Allocated/submitted job {job_id}; waiting for compute node...")
            job = wait_for_node(cluster, job_id, timeout_seconds=wait_timeout)

    if not job.node:
        raise typer.Exit("No compute node available for selected job.")

    update_ssh_config(cluster, job.node, ssh_config)
    console.print(f"SSH alias [bold]{cluster.effective_ssh_alias}[/bold] now points to {job.node}")
    console.print(f"Slurm job: {job.job_id} ({job.state})")

    if not no_launch:
        console.print("Launching VS Code Remote-SSH...")
        launch_vscode(cluster.effective_ssh_alias, remote_path)


@app.command("ssh-config")
def ssh_config_command(
    cluster_name: str,
    node: str = typer.Option(..., "--node", help="Compute node hostname."),
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, "--config"),
    ssh_config: Path = typer.Option(DEFAULT_SSH_CONFIG, "--ssh-config"),
) -> None:
    cluster = load_cluster(cluster_name, config)
    update_ssh_config(cluster, node, ssh_config)
    console.print(f"Updated {ssh_config}: {cluster.effective_ssh_alias} -> {node}")


@app.command()
def attach(
    cluster_name: str,
    job_id: str = typer.Argument(..., help="Active Slurm job id."),
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, "--config"),
    no_launch: bool = typer.Option(False, "--no-launch"),
    ssh_config: Path = typer.Option(DEFAULT_SSH_CONFIG, "--ssh-config"),
    path: str | None = typer.Option(None, "--path"),
) -> None:
    cluster = load_cluster(cluster_name, config)
    job = resolve_job(cluster, job_id)
    if not job.node:
        job = wait_for_node(cluster, job_id)
    if not job.node:
        raise typer.Exit("No compute node available for selected job.")
    update_ssh_config(cluster, job.node, ssh_config)
    console.print(f"Attached {cluster.effective_ssh_alias} to {job.node}")
    if not no_launch:
        launch_vscode(cluster.effective_ssh_alias, path or cluster.remote_project_path)


@app.command()
def cancel(
    cluster_name: str,
    job_id: str = typer.Option(..., "--job-id", help="Slurm job id to cancel."),
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, "--config"),
) -> None:
    cluster = load_cluster(cluster_name, config)
    cancel_job(cluster, job_id)
    console.print(f"Cancelled Slurm job {job_id}")


@app.command()
def doctor(
    cluster_name: str | None = typer.Argument(None, help="Optional cluster profile to test."),
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, "--config", help="Path to config.toml."),
    ssh_config: Path = typer.Option(DEFAULT_SSH_CONFIG, "--ssh-config", help="Path to SSH config."),
    remote: bool = typer.Option(True, "--remote/--no-remote", help="Run login-node Slurm checks when a cluster is provided."),
) -> None:
    console.print(f"Platform: {platform_summary()}")

    results = [
        check_python(),
        check_executable("ssh", ["ssh", "-V"]),
        check_executable("code", ["code", "--version"]),
        check_config_file(config),
        check_ssh_config_writable(ssh_config),
        check_vscode_remote_ssh(),
    ]

    cluster = None
    if cluster_name is not None:
        try:
            cluster = load_cluster(cluster_name, config)
            results.append(type(results[0])("cluster profile", True, cluster_name))
        except Exception as exc:
            results.append(type(results[0])("cluster profile", False, str(exc)))

    if cluster is not None and remote:
        results.append(check_login_reachable(cluster))
        for command in ["squeue", "salloc", "scontrol", "scancel"]:
            results.append(check_remote_command(cluster, command))

    table = Table(title="hpc-jump doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for item in results:
        table.add_row(item.name, "OK" if item.ok else "FAIL", item.detail)
    console.print(table)

    if not all(item.ok for item in results):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

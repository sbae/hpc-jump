from __future__ import annotations

import getpass
import os
import subprocess
from pathlib import Path

from .config import ClusterConfig

DEFAULT_SSH_CONFIG = Path("~/.ssh/config").expanduser()


def _markers(cluster_name: str) -> tuple[str, str]:
    start = f"# >>> hjump managed: {cluster_name}"
    end = f"# <<< hjump managed: {cluster_name}"
    return start, end


def _identity_file(cluster: ClusterConfig) -> str | None:
    if not cluster.identity_file:
        return None
    return str(Path(cluster.identity_file).expanduser())


def _login_alias(cluster: ClusterConfig) -> str:
    return f"{cluster.effective_ssh_alias}-login"


def _secure_config_permissions(path: Path) -> None:
    if os.name != "nt":
        path.chmod(0o600)
        return

    domain = os.environ.get("USERDOMAIN")
    username = os.environ.get("USERNAME") or getpass.getuser()
    principal = f"{domain}\\{username}" if domain else username
    commands = [
        # Establish explicit access before removing inherited rules. If a later
        # command fails, the user must not be locked out of their own config.
        ["icacls", str(path), "/grant:r", f"{principal}:(F)"],
        ["icacls", str(path), "/grant:r", "*S-1-5-18:(F)"],
        ["icacls", str(path), "/grant:r", "*S-1-5-32-544:(F)"],
        ["icacls", str(path), "/inheritance:r"],
        ["icacls", str(path), "/remove", "*S-1-3-4"],
    ]
    for command in commands:
        proc = subprocess.run(command, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            detail = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"Could not secure SSH config permissions: {detail}")


def render_host_block(cluster: ClusterConfig, compute_node: str) -> str:
    identity_file = _identity_file(cluster)
    login_alias = _login_alias(cluster)

    lines = [
        _markers(cluster.name)[0],
        f"Host {login_alias}",
        f"    HostName {cluster.login_host}",
        f"    Port {cluster.port}",
    ]
    if cluster.user:
        lines.append(f"    User {cluster.user}")
    if identity_file:
        lines.append(f"    IdentityFile {identity_file}")

    lines.extend(
        [
            "",
            f"Host {cluster.effective_ssh_alias}",
            f"    HostName {compute_node}",
        ]
    )
    if cluster.user:
        lines.append(f"    User {cluster.user}")
    if identity_file:
        lines.append(f"    IdentityFile {identity_file}")
    lines.extend(
        [
            f"    ProxyJump {login_alias}",
            "    ServerAliveInterval 30",
            "    ServerAliveCountMax 3",
            _markers(cluster.name)[1],
            "",
        ]
    )
    return "\n".join(lines)


def update_ssh_config(
    cluster: ClusterConfig,
    compute_node: str,
    path: Path = DEFAULT_SSH_CONFIG,
) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    start, end = _markers(cluster.name)
    block = render_host_block(cluster, compute_node)

    has_start = start in existing
    has_end = end in existing
    if has_start != has_end:
        raise RuntimeError(
            f"SSH config contains a partial hjump managed block for {cluster.name!r}. "
            "Please repair or remove the managed block markers before retrying."
        )

    if has_start and has_end:
        before, rest = existing.split(start, 1)
        _, after = rest.split(end, 1)
        updated = before.rstrip() + "\n\n" + block + after.lstrip()
    else:
        updated = existing.rstrip() + "\n\n" + block

    path.write_text(updated, encoding="utf-8")
    _secure_config_permissions(path)

from __future__ import annotations

from pathlib import Path

from .config import ClusterConfig


DEFAULT_SSH_CONFIG = Path("~/.ssh/config").expanduser()


def _markers(cluster_name: str) -> tuple[str, str]:
    start = f"# >>> hpc-jump managed: {cluster_name}"
    end = f"# <<< hpc-jump managed: {cluster_name}"
    return start, end


def render_host_block(cluster: ClusterConfig, compute_node: str) -> str:
    lines = [
        _markers(cluster.name)[0],
        f"Host {cluster.effective_ssh_alias}",
        f"    HostName {compute_node}",
    ]
    if cluster.user:
        lines.append(f"    User {cluster.user}")
    lines.extend(
        [
            f"    ProxyJump {cluster.login_host}",
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
    existing = path.read_text() if path.exists() else ""
    start, end = _markers(cluster.name)
    block = render_host_block(cluster, compute_node)

    if start in existing and end in existing:
        before, rest = existing.split(start, 1)
        _, after = rest.split(end, 1)
        updated = before.rstrip() + "\n\n" + block + after.lstrip()
    else:
        updated = existing.rstrip() + "\n\n" + block

    path.write_text(updated)
    path.chmod(0o600)

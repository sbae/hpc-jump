from __future__ import annotations

from pathlib import Path

from .config import ClusterConfig

DEFAULT_SSH_CONFIG = Path("~/.ssh/config").expanduser()


def _markers(cluster_name: str) -> tuple[str, str]:
    start = f"# >>> hpc-jump managed: {cluster_name}"
    end = f"# <<< hpc-jump managed: {cluster_name}"
    return start, end


def _identity_file(cluster: ClusterConfig) -> str | None:
    if not cluster.identity_file:
        return None
    return str(Path(cluster.identity_file).expanduser())


def _login_alias(cluster: ClusterConfig) -> str:
    return f"{cluster.effective_ssh_alias}-login"


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
            f"SSH config contains a partial hpc-jump managed block for {cluster.name!r}. "
            "Please repair or remove the managed block markers before retrying."
        )

    if has_start and has_end:
        before, rest = existing.split(start, 1)
        _, after = rest.split(end, 1)
        updated = before.rstrip() + "\n\n" + block + after.lstrip()
    else:
        updated = existing.rstrip() + "\n\n" + block

    path.write_text(updated, encoding="utf-8")
    path.chmod(0o600)

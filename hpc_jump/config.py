from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path("~/.config/hpc-jump/config.toml").expanduser()

@dataclass(frozen=True)
class ClusterConfig:
    name: str
    login_host: str
    user: str | None = None
    ssh_alias: str | None = None
    default_partition: str | None = None
    default_time: str = "04:00:00"
    default_cpus: int = 1
    default_mem: str = "16G"
    salloc_extra: list[str] = field(default_factory=list)
    remote_project_path: str | None = None
    auto_reuse: bool = True
    job_name_prefix: str = "hpc-jump"

    @property
    def effective_ssh_alias(self) -> str:
        return self.ssh_alias or f"{self.name}-current"

    @property
    def effective_user(self) -> str:
        return self.user or os.getlogin()

def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("rb") as f:
        return tomllib.load(f)

def load_cluster(name: str, config_path: Path = DEFAULT_CONFIG_PATH) -> ClusterConfig:
    raw = load_config(config_path)
    clusters = raw.get("clusters", {})
    if name not in clusters:
        available = ", ".join(sorted(clusters)) or "none"
        raise KeyError(f"Cluster '{name}' not found in {config_path}. Available: {available}")

    data = dict(clusters[name])
    if not data.get("login_host"):
        raise ValueError(f"Cluster '{name}' missing required key: login_host")

    extra = data.get("salloc_extra", []) or []
    if not isinstance(extra, list) or not all(isinstance(x, str) for x in extra):
        raise ValueError("salloc_extra must be a list of strings")

    return ClusterConfig(
        name=name,
        login_host=str(data["login_host"]),
        user=data.get("user"),
        ssh_alias=data.get("ssh_alias"),
        default_partition=data.get("default_partition"),
        default_time=str(data.get("default_time", "04:00:00")),
        default_cpus=int(data.get("default_cpus", 1)),
        default_mem=str(data.get("default_mem", "16G")),
        salloc_extra=extra,
        remote_project_path=data.get("remote_project_path"),
        auto_reuse=bool(data.get("auto_reuse", True)),
        job_name_prefix=str(data.get("job_name_prefix", "hpc-jump")),
    )

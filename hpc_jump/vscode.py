from __future__ import annotations

import subprocess


def launch_vscode(ssh_alias: str, remote_path: str | None = None) -> None:
    target = f"ssh-remote+{ssh_alias}"
    cmd = ["code", "--remote", target]
    if remote_path:
        cmd.append(remote_path)
    subprocess.run(cmd, check=True)

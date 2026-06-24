from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def find_code_executable() -> str | None:
    found = shutil.which("code")
    if found:
        return found

    candidates: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")

    if local_app_data:
        candidates.append(Path(local_app_data) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd")
        candidates.append(Path(local_app_data) / "Programs" / "Microsoft VS Code Insiders" / "bin" / "code-insiders.cmd")
    if program_files:
        candidates.append(Path(program_files) / "Microsoft VS Code" / "bin" / "code.cmd")
    if program_files_x86:
        candidates.append(Path(program_files_x86) / "Microsoft VS Code" / "bin" / "code.cmd")

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def open_in_vscode(path: Path) -> None:
    code = find_code_executable()
    if not code:
        raise FileNotFoundError(
            "Could not find the VS Code command-line launcher 'code'. "
            "Add VS Code to PATH or install the 'code' command-line launcher."
        )
    subprocess.run([code, str(path)], check=True)


def launch_vscode(ssh_alias: str, remote_path: str | None = None) -> None:
    code = find_code_executable()
    if not code:
        raise FileNotFoundError(
            "Could not find the VS Code command-line launcher 'code'. "
            "Add VS Code to PATH or install the 'code' command-line launcher."
        )
    target = f"ssh-remote+{ssh_alias}"
    cmd = [code, "--remote", target]
    if remote_path:
        cmd.append(remote_path)
    subprocess.run(cmd, check=True)

# hpc-jump

Small CLI helper for opening VS Code Remote-SSH on a Slurm compute node instead of on an HPC login node.

The intended workflow is:

1. Use SSH only to run lightweight Slurm commands on the login node.
2. Allocate or discover an interactive Slurm job.
3. Resolve the assigned compute node.
4. Write a managed host entry in `~/.ssh/config` using `ProxyJump` through the login node.
5. Launch VS Code against the compute node alias.

This keeps the VS Code server, file watchers, terminals, and language servers off the login node.

## Requirements

- Python 3.11+
- OpenSSH client available as `ssh`
- VS Code command-line launcher available as `code`
- VS Code Remote-SSH extension: `ms-vscode-remote.remote-ssh`
- A working SSH config or hostname for the HPC login node

## Install

### macOS

Using Homebrew and pipx:

```bash
brew install pipx
pipx ensurepath
pipx install git+https://github.com/sbae/hpc-jump.git
```

Verify:

```bash
ssh -V
code --version
hpc-jump --help
```

If `code` is missing, open VS Code and run `Shell Command: Install 'code' command in PATH` from the command palette.

### Linux

Ubuntu/Debian:

```bash
sudo apt install pipx
pipx ensurepath
pipx install git+https://github.com/sbae/hpc-jump.git
```

Generic Python install:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install git+https://github.com/sbae/hpc-jump.git
```

Verify:

```bash
ssh -V
code --version
hpc-jump --help
```

### Windows

Use native Windows PowerShell, not WSL, for the initial version.

Modern Windows includes OpenSSH. Verify:

```powershell
ssh -V
```

Install pipx:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

Restart PowerShell, then install:

```powershell
pipx install git+https://github.com/sbae/hpc-jump.git
```

Verify:

```powershell
hpc-jump --help
code --version
```

If `code` is missing, reinstall VS Code with the option to add it to PATH, or enable the VS Code command-line launcher.

### Upgrade

```bash
pipx upgrade hpc-jump
```

### Install from a local clone

```bash
git clone https://github.com/sbae/hpc-jump.git
cd hpc-jump
pipx install .
```

or during development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

On Windows PowerShell, activate the venv with:

```powershell
.venv\Scripts\Activate.ps1
pip install -e .
```

## Configure

Copy the example config:

```bash
mkdir -p ~/.config/hpc-jump
cp examples/config.toml ~/.config/hpc-jump/config.toml
```

On Windows PowerShell:

```powershell
mkdir $env:USERPROFILE\.config\hpc-jump
copy examples\config.toml $env:USERPROFILE\.config\hpc-jump\config.toml
```

Edit the cluster profile.

## Check your setup

Local-only checks:

```bash
hpc-jump doctor
```

Check a configured cluster, including login-node Slurm commands:

```bash
hpc-jump doctor my-hpc
```

Skip remote checks:

```bash
hpc-jump doctor my-hpc --no-remote
```

The doctor command checks Python, `ssh`, `code`, the config file, SSH config writability, the VS Code Remote-SSH extension, login-node reachability, and remote Slurm commands.

## Use

```bash
hpc-jump connect my-hpc
```

Useful variants:

```bash
hpc-jump connect my-hpc --time 04:00:00 --cpus 4 --mem 16G
hpc-jump connect my-hpc --existing-job 12345678
hpc-jump attach my-hpc 12345678
hpc-jump ssh-config my-hpc --node compute123
hpc-jump cancel my-hpc --job-id 12345678
```

## Notes

This tool deliberately uses local OpenSSH via `subprocess` rather than a Python SSH library. That preserves your normal SSH behavior, including keys, MFA, Kerberos/GSSAPI, host-key checking, `ProxyJump`, and `ControlMaster`.

WSL is not a first-class target yet. Native Windows PowerShell is the intended Windows path for now.
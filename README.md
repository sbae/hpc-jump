# hpc-jump

Small CLI helper for opening VS Code Remote-SSH on a Slurm compute node instead of on an HPC login node.

The intended workflow is:

1. Use SSH only to run lightweight Slurm commands on the login node.
2. Allocate or discover an interactive Slurm job.
3. Resolve the assigned compute node.
4. Write a managed host entry in `~/.ssh/config` using `ProxyJump` through the login node.
5. Launch VS Code against the compute node alias.

This keeps the VS Code server, file watchers, terminals, and language servers off the login node.

## Install

```bash
pipx install .
```

or during development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configure

Copy the example config:

```bash
mkdir -p ~/.config/hpc-jump
cp examples/config.toml ~/.config/hpc-jump/config.toml
```

Edit the cluster profile.

## Use

```bash
hpc-jump connect my-hpc
```

Useful variants:

```bash
hpc-jump connect my-hpc --time 04:00:00 --cpus 4 --mem 16G
hpc-jump connect my-hpc --existing-job 12345678
hpc-jump ssh-config my-hpc --node compute123
hpc-jump cancel my-hpc --job-id 12345678
```

## Notes

This tool deliberately uses local OpenSSH via `subprocess` rather than a Python SSH library. That preserves your normal SSH behavior, including keys, MFA, Kerberos/GSSAPI, host-key checking, `ProxyJump`, and `ControlMaster`.

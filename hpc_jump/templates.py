from __future__ import annotations


def config_template(cluster_name: str = "my-hpc") -> str:
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in cluster_name)
    return f'''# hpc-jump configuration file.
# Create one [clusters.<name>] section per cluster.

[clusters.{safe_name}]

# Login node hostname or FQDN.
# Examples:
#   login.hpc.edu
login_host = "login.hpc.edu"

# SSH port. Most clusters use 22.
port = 22

# Username used when logging into the cluster.
# Usually your HPC/Linux/Kerberos username, not your email address.
user = "your_username"

# Optional SSH private key file.
# Use forward slashes in TOML paths, even on Windows.
# Good Windows example: C:/Users/your_windows_username/.ssh/id_ed25519
# Bad Windows example:  C:\Users\your_windows_username\.ssh\id_ed25519
# macOS/Linux example: ~/.ssh/id_ed25519
identity_file = "C:/Users/your_windows_username/.ssh/id_ed25519"

# Local SSH alias managed by hpc-jump.
# This is the name VS Code connects to after hpc-jump resolves the compute node.
ssh_alias = "hpc-cpu-short"

# Default Slurm partition/queue.
default_partition = "cpu_short"

# Default interactive allocation duration.
default_time = "04:00:00"

# Default CPU request for the editor session.
default_cpus = 1

# Default total memory request.
# For clusters that require memory per CPU, use salloc_extra below instead.
default_mem = "16G"

# Extra Slurm flags passed to salloc.
# Example: salloc_extra = ["--mem-per-cpu=30G"]
salloc_extra = []

# Slurm job name used for hpc-jump-created sessions.
# auto_reuse only considers RUNNING jobs with this exact Slurm job name.
job_name_prefix = "hpc-jump"

# Experimental: reuse an existing RUNNING hpc-jump Slurm job instead of requesting a new allocation.
# This reuses the Slurm allocation/node, not your prior shell state.
auto_reuse = true

# Optional project folder opened automatically in VS Code.
remote_project_path = "/home/your_username"
'''

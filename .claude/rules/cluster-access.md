# Cluster Access

How to reach nodes on the `bgen-cluster-c` Slurm cluster and how to find one that is free.

## Identify the current node first

Do not assume which node this session is on — it changes between sessions. Determine it at the start of any cluster work:

```bash
hostname                 # e.g. ip-10-20-222-235
hostname -I              # all local addresses
```

Slurm's `ip-A-B-C-D` name is the address with dots swapped for dashes, so the current node's IP falls straight out of the hostname:

```bash
hostname | sed 's/^ip-//; s/-/./g'      # ip-10-20-222-235 -> 10.20.222.235
```

Cross-reference that IP against the table at the bottom to get the `vision-node-NNN` label. The three names are one machine written three ways:

```
vision-node-NNN  ->  10.20.A.B  ->  ip-10-20-A-B
      ^                  ^               ^
 local Mac only    actual address   what Slurm reports
```

## Never SSH to the node you are already on

SSHing to the current node succeeds, but it loops back to the shell you already have and buys nothing. Before any SSH, check whether the target address is bound locally:

```bash
if ip -4 -o addr show | grep -qw "<target-ip>"; then
  echo "local — run the command directly, no ssh"
else
  ssh -o BatchMode=yes -o ConnectTimeout=10 lavanya.venna@<target-ip> '<cmd>'
fi
```

When the target is local, run the command directly: it is the local filesystem, local GPUs, and local processes, which is faster and avoids the SSH wrapper entirely.

Note that a node has several addresses (`hostname -I` typically shows a `10.20.x.x` cluster address alongside `10.42.x.x`, `169.254.x.x`, and `172.17.x.x`). Match against the full `ip addr` output as above rather than against a single IP.

## Logging in to another node

The `vision-node-NNN` aliases exist **only in the user's local Mac `~/.ssh/config`**, where they route through `ProxyJump bgen-cluster-c` (an AWS SSM session). That file is not on the cluster, so:

- `ssh vision-node-0NN` **fails here** — "Could not resolve hostname". This is expected, not a fault.
- **Always SSH by IP**, and no ProxyJump is needed. Compute nodes reach each other directly.

```bash
ssh lavanya.venna@<ip>
```

Key auth is already set up via `~/.ssh/authorized_keys`, so no password is required. For non-interactive use, which is the normal mode here:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 lavanya.venna@10.20.220.93 'hostname; nvidia-smi'
```

Use `BatchMode=yes` so a broken login fails fast instead of hanging on a prompt, and wrap calls in `timeout` since a wedged node can otherwise stall.

Note that an interactive shell cannot be held open across tool calls. Run each remote command as `ssh host 'cmd'`; for multi-step work, chain with `&&` or pass a heredoc script.

### Host key errors

A node reimaged since its key was cached fails with `REMOTE HOST IDENTIFICATION HAS CHANGED`. This is a stale `known_hosts` entry from the node's rebuild, not an attack. Confirm the IP is a legitimate cluster node, then drop the old key:

```bash
ssh-keygen -f ~/.ssh/known_hosts -R <ip>
```

`10.20.202.110` (node 001) was in this state as of 2026-08-30.

Because `$HOME` is shared (below), `known_hosts` is shared too: a stale key affects every node, and clearing it once clears it everywhere.

For a first-time connection to a node with no cached key, add `-o StrictHostKeyChecking=accept-new`. Do not use `StrictHostKeyChecking=no` — it also silently accepts *changed* keys.

## $HOME is shared across all nodes

`/home/lavanya.venna` is network-mounted and identical on every node — verified by writing a file on one node and reading it from another. So `~/.ssh/config`, `~/.ssh/known_hosts`, and `~/.ssh/authorized_keys` are the same everywhere, which is why key auth works from any node to any node without extra setup.

Practical consequence: do not copy files between nodes over `scp` when both paths are under `$HOME` — they are already the same file. Node-local paths such as `/tmp` are *not* shared.

## Checking which nodes are available

Every node is an 8x H100 `ml.p5.48xlarge`. Partitions are `dev` (default) and `ml.p5.48xlarge`; both contain the same machines.

Free nodes:

```bash
sinfo -t idle -o "%N %t %G"
```

Everything, grouped by state:

```bash
sinfo -o "%P %a %D %t %N"
```

Per-node GPU usage — the most useful view, since `alloc` nodes may still have GPUs free:

```bash
sinfo -N -O "NodeHost:20,StateLong:12,Gres:16,GresUsed:20"
```

`GresUsed` shows `gpu:h100:8(IDX:0-7)` for a fully busy node and `gpu:h100:0` for an empty one.

Who is running what, and detail on one node:

```bash
squeue -o "%.10i %.12u %.10P %.8T %.10M %R"
scontrol show node $(hostname)          # the current node
scontrol show node ip-10-20-220-93      # a specific one
```

**Read the state before using a node.** `idle` is free, `alloc` is in use, `drain` and `fail` are unhealthy — skip them; `drain`/`fail` nodes may accept SSH while being unfit for work.

Prefer submitting through Slurm (`srun` / `sbatch`) over SSHing onto a node and running directly. Bypassing the scheduler means landing on GPUs another job has been allocated.

## The name-to-IP map is incomplete

The Mac config lists 35 nodes; Slurm reports **45**. Treat `sinfo` as the source of truth.

- `10.20.237.24` (listed as node 026) is **not in Slurm** — stale entry, do not rely on it.
- 11 nodes in Slurm have **no `vision-node` alias**: `ip-10-20-135-108`, `144-213`, `155-194`, `176-23`, `179-184`, `181-135`, `183-3`, `184-114`, `188-73`, `197-208`, `198-82`. Reach these by IP, converting the name: `ip-10-20-135-108` -> `10.20.135.108`.

| Node | IP | Node | IP |
|---|---|---|---|
| 001 | 10.20.202.110 | 019 | 10.20.227.40 |
| 002 | 10.20.204.252 | 020 | 10.20.227.52 |
| 003 | 10.20.205.50 | 021 | 10.20.227.97 |
| 004 | 10.20.208.160 | 022 | 10.20.229.109 |
| 005 | 10.20.211.172 | 023 | 10.20.230.169 |
| 006 | 10.20.213.4 | 024 | 10.20.233.75 |
| 007 | 10.20.213.80 | 025 | 10.20.235.133 |
| 008 | 10.20.214.12 | 026 | 10.20.237.24 (stale) |
| 009 | 10.20.216.9 | 027 | 10.20.238.24 |
| 010 | 10.20.218.142 | 028 | 10.20.238.191 |
| 011 | 10.20.218.187 | 029 | 10.20.239.162 |
| 012 | 10.20.218.215 | 030 | 10.20.239.233 |
| 013 | 10.20.220.93 | 031 | 10.20.241.38 |
| 014 | 10.20.222.235 | 032 | 10.20.241.80 |
| 015 | 10.20.223.43 | 033 | 10.20.193.129 |
| 016 | 10.20.224.174 | 034 | 10.20.196.218 |
| 017 | 10.20.225.177 | 035 | 10.20.173.10 |
| 018 | 10.20.227.19 | | |

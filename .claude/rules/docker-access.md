# Docker Access

**Nothing runs on a bare node.** Scripts, training jobs, and Python must execute inside the user's Docker container. Running them on the host is wrong even when it appears to work — the host lacks the project environment.

See [cluster-access.md](cluster-access.md) for reaching nodes; this file governs everything after that.

## Required first step: confirm a container exists

Before running any command for the user's work, check. Do not skip this because a container was present earlier in the session or on another node.

```bash
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep -i "lavanya.venna"
```

Two container names are acceptable, in this order of preference:

1. `patram-ingest-pipeline-lavanya.venna`
2. `patram-data-engine-lavanya.venna`

Use the first one that is present **and** shows `Up` in `STATUS`.

## If no container exists: stop and report

This is a hard stop, not something to work around.

If neither container is present — or one exists but is `Exited` — **do not** run the work on the host, **do not** start, create, restart, or otherwise modify a container, and **do not** substitute another user's container (many exist on these nodes; they belong to other people).

Report back plainly:

> There is no Docker container for you on `<node>`. I checked for `patram-ingest-pipeline-lavanya.venna` and `patram-data-engine-lavanya.venna`; neither is running. I can't proceed until you create one.

Include which node was checked and what `docker ps -a` actually showed — an `Exited` container is a different problem from a missing one, and the user needs to know which they are fixing.

Then wait. Creating containers is the user's call.

## Running commands in the container

The interactive form is:

```bash
docker exec -it patram-ingest-pipeline-lavanya.venna bash
```

**`-it` does not work from a tool call** — it fails with `the input device is not a TTY`, and an interactive shell cannot be held open across calls anyway. Drop `-it` and pass the command instead:

```bash
docker exec patram-ingest-pipeline-lavanya.venna bash -lc '<command>'
```

Use `bash -lc` so the login shell initialises the environment (conda, venv, `PATH`) the same way the interactive shell would. For multi-step work, chain with `&&` or pass a heredoc script — do not try to keep a session alive between calls, because each `docker exec` is a fresh process and shell state does not carry over. Anything that must persist has to be written to a file.

The default working directory inside the container is `/code`, so `cd` explicitly:

```bash
docker exec patram-ingest-pipeline-lavanya.venna bash -lc 'python3 train.py'
```

`/fsxvision_new` and the H100s are visible inside the container.

## Containers are node-local

The Docker daemon is per-node. `$HOME` is shared across nodes, but **containers are not** — a container on one node does not exist on another. Verified: `patram-ingest-pipeline-lavanya.venna` runs on `ip-10-20-222-235`, while `ip-10-20-220-93` has no container for this user at all.

So re-run the check after moving to a different node. To reach a container on a remote node, nest the calls:

```bash
ssh -o BatchMode=yes lavanya.venna@<ip> \
  'docker exec patram-ingest-pipeline-lavanya.venna bash -lc "cd /fsxvision_new/lavanya.venna/diffusion && <command>"'
```

Mind the quoting: outer single quotes for `ssh`, inner double quotes for `docker exec`.

## Observed state (2026-08-30, node ip-10-20-222-235)

- `patram-ingest-pipeline-lavanya.venna` — **Up 4 weeks**. Use this one.
- `patram-data-engine-lavanya.venna` — **absent**. `patram-data-engine-srihari.bandarupalli` exists but belongs to another user; do not touch it.
- Also present for this user: `vlm-ingest-pipeline-lavanya.venna` (Up 6 weeks), which is not one of the two sanctioned names — do not use it unless the user says so.

This is a snapshot, not a substitute for checking. Verify at the start of each session.

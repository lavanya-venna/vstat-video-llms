# Python Environments

All of the user's environments live under:

```
/fsxvision_new/lavanya.venna/environments
```

They are plain Python **venvs**, not conda. Activate with `source <env>/bin/activate`.

## Activate inside the container, never on the host

Environments must be activated **inside the Docker container** (see [docker-access.md](docker-access.md)), not on the host node. This is not a style preference — activating on the host silently gives a broken interpreter.

The reason: these venvs were built with the container's `/usr/bin/python3.12`, so their packages sit in `lib/python3.12/site-packages`. But `bin/python3` is a symlink to `/usr/bin/python3`, which resolves to **3.10.12 on the host** and **3.12.3 in the container**. On the host you therefore get a 3.10 interpreter that cannot see the 3.12 site-packages, and imports fail or silently pick up the wrong versions.

Correct form:

```bash
docker exec patram-ingest-pipeline-lavanya.venna bash -lc \
  'source /fsxvision_new/lavanya.venna/environments/<env>/bin/activate && python <script>.py'
```

Activation does not persist between calls — each `docker exec` is a fresh process, so `source` must be part of every command.

Sanity check after activating:

```bash
python --version && which python
```

`which python` must point under the env directory, and the version must match the table below.

## Available environments

`/fsxvision_new` is shared storage, so these are identical from every node.

| Environment | Python | Notes |
|---|---|---|
| `gemma4` | 3.12 | |
| `gemma4_new` | 3.12 | Newer of the two; torch 2.11.0+cu129, CUDA verified working |
| `ocr_env_vllm` | 3.12 | |
| `sam3_env` | 3.12 | |
| `sam3_env_new` | 3.12 | **Incomplete — no `bin/`, cannot be activated** |
| `transformer-training` | 3.12 | **No `bin/python`; `bin/` has scripts but no interpreter** |
| `translation_data_engine_env` | 3.10 | Built against 3.10, not 3.12 |
| `visual-grounding-env` | 3.10 | Built against 3.10, not 3.12 |
| `vllm_env` | 3.12 | |
| `vllm_env_1` | 3.12 | Sparse (92 packages); owned by `root`, so not writable |

`_patram_fs_backup_20260814-000153/` is a backup directory, not an environment. Ignore it.

### Do not assume which environment to use

The names suggest purposes, but several overlap (`gemma4` / `gemma4_new`, `sam3_env` / `sam3_env_new`, `vllm_env` / `vllm_env_1`). If the task does not name one and it is not obvious from the code being run, **ask** rather than guessing — picking the wrong one wastes a long dependency-resolution cycle.

### Two are broken

`sam3_env_new` and `transformer-training` have no usable interpreter. If a task calls for either, report that instead of falling back to a similar-looking environment.

## Adding packages

Install only into an activated env, and never with `sudo`:

```bash
docker exec patram-ingest-pipeline-lavanya.venna bash -lc \
  'source /fsxvision_new/lavanya.venna/environments/<env>/bin/activate && pip install <pkg>'
```

`vllm_env_1` is root-owned and will fail on write; the rest are user-owned. Because the directory is shared storage, an install changes that environment for **every node and every session** — confirm with the user before adding to or upgrading a shared env.

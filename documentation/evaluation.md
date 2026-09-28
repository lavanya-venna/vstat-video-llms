# Qwen3.5-9B VSTAT Evaluation

How `Qwen/Qwen3.5-9B` was evaluated on the VSTAT (Visual State Tracking) benchmark, and why it's set up this way.

## Serving the model

An earlier attempt loaded the model in-process (`transformers`, `device_map="auto"`) via lmms_eval's `qwen3_5` model wrapper. This was too slow to be usable: `device_map="auto"` naively pipeline-shards the model across all 8 GPUs, forcing a cross-GPU sync at every decode step — a fixed latency cost that doesn't shrink with model size. A 3-sample smoke test ran 25+ minutes without finishing a single sample.

Instead, the model is **served with vLLM**, in its own `tmux` session, giving real tensor-parallel inference with continuous batching instead of naive per-token cross-GPU pipeline sync:

```bash
vllm serve Qwen/Qwen3.5-9B \
  --tensor-parallel-size 8 \
  --port 8000 \
  --max-model-len 32768 \
  --dtype auto \
  --default-chat-template-kwargs '{"enable_thinking": false}'
```

Run from the `vllm_env` environment (vLLM 0.17.1). `--default-chat-template-kwargs` turns off Qwen3.5's thinking mode by default for every request. This was tested both ways on the same 6-sample slice: with thinking on, generation used 22,024 output tokens and took 2m15s; with it off, 12 output tokens and 11 seconds — a ~12x speedup for the same accuracy (both scored 0.30-0.33 on that slice). Thinking mode was producing long step-by-step reasoning as plain output text rather than a concise final answer, which this task's strict answer-format instructions don't need.

## Running the evaluation

With the server up in one tmux session, the eval client runs in a **second, separate tmux session**, hitting the server's OpenAI-compatible endpoint over HTTP:

```bash
bash src/evaluation/qwen35_9b/run.sh
```

which runs:

```bash
python -m lmms_eval \
  --include_path "$(pwd)/lmms_eval/tasks" \
  --model openai \
  --model_args "model_version=Qwen/Qwen3.5-9B,base_url=http://localhost:8000/v1,api_key=EMPTY,num_concurrent=32,timeout=240,video_as_url=True" \
  --tasks vstat --batch_size 1 \
  --output_path src/evaluation/qwen35_9b \
  --log_samples
```

Run from the `gemma4_new` environment (has `lmms_eval`/the `vstat` task installed). Notes on the `model_args`:
- `api_key=EMPTY` — the `openai` Python SDK refuses to construct a client without *some* key, even for a local server that doesn't check it.
- `video_as_url=True` — sends each clip as a base64 data-URL so vLLM does its own native frame/pixel sampling server-side, rather than lmms_eval pre-sampling a fixed 10 frames client-side.
- `num_concurrent=32` — tuned up from an initial `8` after confirming GPU KV-cache usage stayed under 1% at that concurrency; 32 kept the server comfortably saturated without erroring.

## The speedup

| Approach | Estimated/actual time for full 1469-doc run |
|---|---|
| In-process `transformers` (`device_map="auto"`) | **~13.6 hours** (extrapolated: a 3-sample smoke test ran 25+ min without finishing even one sample) |
| vLLM-served (this run) | **~10 minutes** |

## Environments used

| Role | Environment | Key versions |
|---|---|---|
| vLLM server | `vllm_env` | vLLM 0.17.1 |
| Eval client | `gemma4_new` | transformers 5.14.1, torch 2.11.0+cu129 |

Both under `/fsxvision_new/lavanya.venna/environments/`.

## Dataset used

`vstat_data/vstat_qa_available.json` — **1469 entries**, the pre-filtered subset of the raw 1500-entry `vstat_qa_clean.json` containing only questions whose video file was actually downloaded. (The full `vstat_qa_clean.json` references some videos that don't exist locally; running against it hard-crashes on the first missing file with `AssertionError: Missing video file: ...` — this was caught after the first attempt.)

## Final metrics

From `metrics.json` (1468/1469 samples completed — one dropped from an isolated per-request error):

| Metric | Value |
|---|---|
| ALL_Score_avg | 0.3534 |
| MCQ_ACC | 0.3592 |
| Numeric_MRA | 0.3501 |

## Flow to execute

1. Start the vLLM server (tmux session 1, `vllm_env`) with the command above.
2. Wait for it to respond: `curl -sf http://localhost:8000/v1/models`.
3. Run the eval (tmux session 2, `gemma4_new`): `bash src/evaluation/qwen35_9b/run.sh`.
4. Tear down the server once the run finishes — it holds all 8 GPUs for as long as it's alive:
   ```bash
   pkill -f "vllm serve"
   ```

Artifacts: `src/evaluation/qwen35_9b/run.sh` (eval command), `eval.log` (full run log), `metrics.json` (aggregated results), `results_vstat.jsonl` (per-sample outputs).

---

# Molmo2-O-7B VSTAT Evaluation

How `allenai/Molmo2-O-7B` was evaluated on VSTAT, following the same vLLM-served pattern as Qwen3.5-9B above.

## Serving the model

Molmo2-O-7B was deferred earlier in this project: its HF model card pins `transformers==4.57.1`, which conflicted with the newer `transformers` in `gemma4_new` used for in-process wrappers. That's irrelevant for vLLM serving, since vLLM ships its own native Molmo2 implementation (`vllm/model_executor/models/molmo2.py`, registered as `Molmo2ForConditionalGeneration`) independent of the installed `transformers` version.

```bash
vllm serve allenai/Molmo2-O-7B \
  --tensor-parallel-size 8 \
  --port 8000 \
  --max-model-len 32768 \
  --dtype auto \
  --trust-remote-code
```

Run from `vllm_env` (same environment as Qwen3.5-9B). No `--default-chat-template-kwargs` flag is needed — Molmo2 isn't a reasoning/thinking-mode model, so it already gives short, direct answers by default. `--trust-remote-code` is required for Molmo2's custom modeling code.

One real constraint hit here: Molmo2-O-7B's native context is much smaller than Qwen3.5-9B's. Requesting `--max-model-len 32768` gets silently clamped by vLLM to the model's actual supported length, **8100 tokens** (confirmed via `curl http://localhost:8000/v1/models`, which reports the effective `max_model_len`). This was fine in practice — average request in testing used ~2,900 input tokens with just a few output tokens (Molmo2 gives terse direct answers to this task's strict-format prompts), comfortably inside 8100.

## The concurrency crash, and what actually caused it

The first full-run attempt used `num_concurrent=32` (the value that worked well for Qwen3.5-9B) and produced a wave of `500 Internal Server Error` responses partway through a 30-sample test. Checking only the eval client's log at the time made this look like a connection/concurrency-ceiling problem, but checking the **server's** log revealed the real cause: a genuine CUDA out-of-memory crash inside vLLM's engine —

```
RuntimeError: Worker failed with error 'CUDA out of memory. Tried to allocate 104.00 MiB.
GPU 0 has a total capacity of 79.18 GiB of which 72.25 MiB is free. ...'
```

32 concurrent video-heavy requests pushed one GPU's KV-cache/encoder-cache allocation past what fit in memory (Molmo2's smaller `max_model_len` doesn't reduce the per-request encoder-cache cost of processing video frames). The engine died fatally (`EngineDeadError`), which is what turned every in-flight and subsequent request into a 500 — not a soft rate limit, the server process actually exited. `num_concurrent=8` (validated separately, no errors) was used for the real full run instead.

## GPU contention forced a node change mid-run

Partway through this evaluation, `vision-node-008` (where the server had been running) started showing all 8 GPUs at 100% utilization and ~43-45GB used each, but with **no matching process visible** in the container's own `ps`/`nvidia-smi` output — consistent with an external, unrelated job landing on the same shared node, invisible across container/PID-namespace boundaries. Rather than fight for GPU time there, the server was moved to **vision-node-014** (`10.20.222.235`), reusing the same `patram-ingest-pipeline-lavanya.venna` container (containers are node-local, but this container had also been set up there previously). `/fsxvision_new` is shared network storage, so the repo, dataset, and environments were already in place with no re-setup needed.

## Running the evaluation

Same two-tmux-session pattern as Qwen3.5-9B, on node-014's container this time: the server ran in tmux session `molmo_server`, the eval client in a separate session `eval_molmo`.

```bash
bash src/evaluation/molmo2_o_7b/run.sh
```

which runs:

```bash
python -m lmms_eval \
  --include_path "$(pwd)/lmms_eval/tasks" \
  --model openai \
  --model_args "model_version=allenai/Molmo2-O-7B,base_url=http://localhost:8000/v1,api_key=EMPTY,num_concurrent=8,timeout=240,video_as_url=True" \
  --tasks vstat --batch_size 1 \
  --output_path src/evaluation/molmo2_o_7b \
  --log_samples
```

Run from `gemma4_new`, same `model_args` conventions as Qwen3.5-9B (`api_key=EMPTY`, `video_as_url=True`), with `num_concurrent=8` instead of `32` for the reason above.

## Environments used

| Role | Environment | Key versions |
|---|---|---|
| vLLM server | `vllm_env` | vLLM 0.17.1 |
| Eval client | `gemma4_new` | transformers 5.14.1, torch 2.11.0+cu129 |

Same environment pair as Qwen3.5-9B, run on vision-node-014 instead of vision-node-008 (mid-run node change, see above).

## Dataset used

Same as Qwen3.5-9B: `vstat_data/vstat_qa_available.json` (1469 entries, pre-filtered to videos actually downloaded).

## Final metrics

From `metrics.json` (1469/1469 samples completed — no drops this time):

| Metric | Value |
|---|---|
| ALL_Score_avg | 0.3264 |
| MCQ_ACC | 0.3516 |
| Numeric_MRA | 0.3122 |

## Qwen3.5-9B vs. Molmo2-O-7B

| Metric | Qwen3.5-9B | Molmo2-O-7B |
|---|---|---|
| ALL_Score_avg | 0.3534 | 0.3264 |
| MCQ_ACC | 0.3592 | 0.3516 |
| Numeric_MRA | 0.3501 | 0.3122 |
| Samples completed | 1468/1469 | 1469/1469 |
| Safe `num_concurrent` | 32 | 8 |

Qwen3.5-9B scored modestly higher across all three metrics on this run, and tolerated much higher request concurrency before hitting memory pressure.

## Flow to execute

1. Confirm/create the `patram-ingest-pipeline-lavanya.venna` container on the target node (containers are node-local).
2. Start the vLLM server (tmux session 1, `vllm_env`) with the command above; confirm the effective `max_model_len` via `curl http://localhost:8000/v1/models` rather than assuming the requested value took effect.
3. Run the eval (tmux session 2, `gemma4_new`): `bash src/evaluation/molmo2_o_7b/run.sh`.
4. Tear down the server once the run finishes:
   ```bash
   pkill -f "vllm serve"
   ```

Artifacts: `src/evaluation/molmo2_o_7b/run.sh` (eval command), `eval.log` (full run log), `metrics.json` (aggregated results), `results_vstat.jsonl` (per-sample outputs).

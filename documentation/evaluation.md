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

---

# vstat_prompt1: the structured-answer prompt, and the 4096-token cap

`vstat_prompt1` is a variant of the `vstat` task that asks the model to answer in a structured `PLAN` / `RECORD` / `READ` / `ANSWER` format instead of a bare number or letter — writing out its state-tracking (entities, events, running counts) before giving a final `ANSWER:` line, so the reasoning is visible and auditable. The task lives in `src/evaluation/tasks/vstat_prompt1/`, reusing `vstat`'s scoring/video-loading logic (`vstat/lmms_eval/tasks/vstat/utils.py`) but with its own prompt template and a two-step scorer (`process_results_prompt1` in `src/evaluation/tasks/vstat_prompt1/utils.py`): it extracts the value after the final `ANSWER:` line and scores that; only if no `ANSWER:` line exists does it fall back to scanning the *entire* raw response for the last integer/letter.

## Why the output-token cap needed raising

The full `qwen35_9b_prompt1` run (1,469 docs) initially scored `Numeric_MRA = 0.0` across sampled wrong-numeric-answer rows in `analysis.jsonl`. Investigating row 6 of the `qwen35_9b_prompt1_smoke` run's `samples_vstat_prompt1.jsonl` (doc_id 5, a basketball-possession-count question, target `6`) showed why: the response was cut off mid-`RECORD` section —

```
...pass(player_4, player_5) from 215.0s to 217.0s
UPD: possession = {player_5} | player_5
```

— with `token_counts.output_tokens` reading exactly `4096` and no `ANSWER:` line anywhere. The `PLAN`/`RECORD` format writes one `EVT`+`UPD` pair per event in the video, which for event-dense videos (dozens of passes/possessions) consumes thousands of tokens before ever reaching `READ`/`ANSWER` — and 4096 wasn't enough room.

The 4096 figure turned out to be **hardcoded in the vendored `vstat/` package**, not the task config: `vstat/lmms_eval/models/simple/openai.py:564` does

```python
max_new_tokens = min(request_gen_kwargs.get("max_new_tokens", 1024), 4096)
```

which silently clamps every request to 4096 regardless of what the task asks for — `vstat_prompt1.yaml` already specifies `generation_kwargs.max_new_tokens: 16384`, but that value never reaches the server because of this `min(..., 4096)`.

**A second, independent bug compounds this:** when there's no `ANSWER:` line, `process_results_prompt1`'s fallback scans the *whole* truncated response for the last integer via `re.findall(r"-?\d+", ...)`. In the doc_id 5 example above, that regex's last match was the `5` in the entity label `player_5` — not a computed answer at all. Against target `6`, that accidental `5` scored `Numeric_MRA = 0.7` (relative error 16.7%, clears most MRA thresholds) — a real-looking but entirely spurious score. This means **any score derived from a truncated response with no `ANSWER:` line is unreliable**, not just the ones that land at `0.0`.

## How the cap was raised — without editing `vstat/`

`vstat/` is a vendored/pinned dependency; rather than edit `openai.py` there, the fix intercepts the request one layer up, in the `openai` Python SDK itself, from two new files that live entirely outside `vstat/`:

- **`src/evaluation/qwen35_9b_prompt1/patch_max_tokens.py`** — monkeypatches `openai.resources.chat.completions.completions.Completions.create`. Any outgoing request whose `max_tokens`/`max_completion_tokens` equals the hardcoded clamp value (`4096`) gets rewritten to `RAISED_CAP` (currently **19000**, overridable via the `VSTAT_MAX_TOKENS_CAP` env var) immediately before the SDK sends it. Since `vstat`'s code still computes and passes `max_tokens=4096` internally, this only touches the value that actually leaves the process.
- **`src/evaluation/qwen35_9b_prompt1/run_patched.py`** — a drop-in replacement for `python -m lmms_eval`: it imports `patch_max_tokens` first, then calls `lmms_eval.cli.dispatch.main()`, which reads `sys.argv[1:]` the same way the `-m` invocation does — so all existing `--model`/`--tasks`/... flags keep working unchanged.
- **`src/evaluation/qwen35_9b_prompt1/run.sh`** was updated to call `run_patched.py` in place of `python -m lmms_eval`.

Verified in isolation (no real server needed): calling the patched `Completions.create` with `max_tokens=4096` rewrites it to the configured cap before it reaches the SDK's request-building code, while any other value (e.g. an explicit `2048`) passes through untouched.

### Why 19000, not higher

The real ceiling isn't an arbitrary constant — it's the vLLM server's context window. The server is launched with `--max-model-len 32768`, and that figure is `input_tokens + output_tokens` combined, not output alone. The longest prompt observed across the full `qwen35_9b_prompt1` run used **13,471 input tokens**, which leaves at most `32768 - 13471 = 19,297` tokens of headroom for output before the server would reject the request with a context-length error. `19000` was chosen to sit just under that worst-case headroom — a much higher fixed number (e.g. `32768`) would work for short-prompt docs but risk hard failures on the longest ones, given the server's `max_model_len` wasn't changed.

## Observations, cap-by-cap

An 8-sample smoke test (`src/evaluation/qwen35_9b_prompt1_smoke/`) was run three times against the same live vLLM server, raising only the cap between runs:

| Cap | ALL_Score_avg / Numeric_MRA | Docs still hitting the cap (no `ANSWER:`) |
|---|---|---|
| 4096 (original, unpatched) | — (not run standalone; full-run rows all scored near 0) | most event-dense docs |
| 16384 | 0.3875 | doc_id 2, doc_id 5 |
| 19000 | 0.6375 | doc_id 2, doc_id 5, **and now doc_id 6** |

Raising 4096 → 16384 → 19000 fixed most samples (6 of 8 completed cleanly under 700 output tokens with a real `ANSWER:` line) and roughly doubled the aggregate score once genuinely-completed responses could be scored honestly instead of via the truncated-response fallback. But it did **not** fully resolve the problem:

- doc_id 2 and doc_id 5 still ran all the way to the cap at both 16384 and 19000, without ever reaching `ANSWER:`.
- doc_id 6 — which completed fine under *both* 4096 and 16384 — newly hit the 19000 cap and truncated. Same prompt, same video, same model, temperature 0 (nominally deterministic); this is unexplained and worth further investigation before trusting a higher cap as a monotonic fix.

## What we think the problem is

Two distinct issues, not one:

1. **Format cost scales with event count, and some videos exceed any reasonable budget.** The `PLAN`/`RECORD` format spends real tokens per event (`EVT: ...` + `UPD: ...`, one pair per event, no merging or skipping allowed by the prompt's own rules). For videos with many possession changes, passes, or shots, this can apparently exceed even a 19k-token budget. Raising the cap further is bounded by the server's `--max-model-len 32768` (see above) — meaningfully more headroom would require restarting the server with a larger context window, which needs the model to actually support that length and is a shared-resource change beyond just this eval. The other lever is shortening the format itself (e.g. more compact `EVT`/`UPD` encoding) rather than continuing to raise the cap.
2. **The whole-response fallback in `process_results_prompt1` produces unreliable scores whenever there's no `ANSWER:` line**, as shown by doc_id 5's spurious `0.7` from matching a digit inside an entity label (`player_5`) rather than a real answer. This is a scoring-logic issue independent of the token cap: even with a much larger cap, any doc that still truncates will keep getting a coincidental rather than meaningful score. This wasn't changed as part of this investigation — flagging it as a separate follow-up.

## How to run the smoke test

Two tmux sessions in the `patram-ingest-pipeline-lavanya.venna` container on whichever node the server is on (containers are node-local; confirm before assuming a session from a previous run is still there):

1. **Server session** (`vllm_env`) — same `vllm serve` command as the main Qwen3.5-9B run (see above); confirm it's up with `curl -sf http://localhost:8000/v1/models`.
2. **Eval session** (`gemma4_new`), in a *separate* tmux session so it doesn't clobber the server's pane:
   ```bash
   bash /fsxvision_new/lavanya.venna/v_models/src/evaluation/qwen35_9b_prompt1_smoke/run_smoke_test.sh
   ```
   which runs the patched launcher with `--limit 8`:
   ```bash
   python /fsxvision_new/lavanya.venna/v_models/src/evaluation/qwen35_9b_prompt1/run_patched.py \
     --include_path /fsxvision_new/lavanya.venna/v_models/src/evaluation/tasks/vstat_prompt1 \
     --model openai \
     --model_args "model_version=Qwen/Qwen3.5-9B,base_url=http://localhost:8000/v1,api_key=EMPTY,num_concurrent=8,timeout=240,video_as_url=True" \
     --tasks vstat_prompt1 --batch_size 1 --limit 8 \
     --output_path /fsxvision_new/lavanya.venna/v_models/src/evaluation/qwen35_9b_prompt1_smoke \
     --log_samples
   ```
   To change the cap without editing any file, set `VSTAT_MAX_TOKENS_CAP` before running (e.g. `export VSTAT_MAX_TOKENS_CAP=24576`).

Each run creates a new `<output_path>/Qwen__Qwen3.5-9B/<timestamp>/` folder (lmms_eval's fixed behavior — no CLI flag disables it), so re-running the smoke test never overwrites a previous run's `samples_vstat_prompt1.jsonl`/`results.json`.

Artifacts: `src/evaluation/qwen35_9b_prompt1/patch_max_tokens.py` (the patch), `src/evaluation/qwen35_9b_prompt1/run_patched.py` (patched launcher), `src/evaluation/qwen35_9b_prompt1_smoke/run_smoke_test.sh` (smoke-test entry point), `src/evaluation/qwen35_9b_prompt1_smoke/eval_smoke_patched.log` (latest run log).

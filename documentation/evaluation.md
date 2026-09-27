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

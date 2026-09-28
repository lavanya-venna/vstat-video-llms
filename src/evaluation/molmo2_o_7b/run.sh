#!/usr/bin/env bash
set -euo pipefail

# NOTE: lmms_eval always writes into <output_path>/<model_name_sanitized>/<timestamp>/
# (hardcoded in vstat/lmms_eval/loggers/evaluation_tracker.py, no CLI flag to
# disable it) -- re-running this script will recreate that nested subfolder
# under molmo2_o_7b/ rather than overwrite results_vstat.jsonl/metrics.json
# directly. After a re-run, move/rename the new files out the same way this
# run's were: samples_vstat.jsonl -> results_vstat.jsonl, results.json -> metrics.json.

source /fsxvision_new/lavanya.venna/environments/gemma4_new/bin/activate

cd /fsxvision_new/lavanya.venna/v_models/vstat

export VSTAT_QA_PATH=/fsxvision_new/lavanya.venna/v_models/vstat_data/vstat_qa_available.json
export VSTAT_VIDEO_ROOT=/fsxvision_new/lavanya.venna/v_models/vstat_data

python -m lmms_eval \
  --include_path "$(pwd)/lmms_eval/tasks" \
  --model openai \
  --model_args "model_version=allenai/Molmo2-O-7B,base_url=http://localhost:8000/v1,api_key=EMPTY,num_concurrent=8,timeout=240,video_as_url=True" \
  --tasks vstat --batch_size 1 \
  --output_path /fsxvision_new/lavanya.venna/v_models/src/evaluation/molmo2_o_7b \
  --log_samples 2>&1 | tee /fsxvision_new/lavanya.venna/v_models/src/evaluation/molmo2_o_7b/eval.log

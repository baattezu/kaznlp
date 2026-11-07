#!/bin/sh
# Data-pipeline quality gate, run INSIDE the runtime image by Jenkins:
#   docker run --rm -i -e MIN_F1=0.3 kaznlp:<tag> sh -s < ci/quality_gate.sh | tar -xf - -C pipeline
# clean -> split -> baseline -> evaluate on the bundled sample data. Logs go to stderr,
# the JSON reports are streamed to stdout as a tar archive. `kaznlp evaluate --min-f1`
# exits with 1 when macro-F1 is too low, which fails the script and the Jenkins stage.
set -eu
MIN_F1="${MIN_F1:-0.3}"
cd "$(mktemp -d)"
{
  kaznlp clean /app/data/sample.jsonl clean.jsonl > clean_stats.json
  cat clean_stats.json
  kaznlp split clean.jsonl split
  for task in sentiment risk; do
    kaznlp baseline split/train.jsonl split/test.jsonl "pred_$task.jsonl" --label-field "$task"
    kaznlp evaluate "pred_$task.jsonl" --label-field "$task" --min-f1 "$MIN_F1" \
      --output "report_$task.json" > /dev/null
    python -c "import json; r = json.load(open('report_$task.json')); \
print('$task: macro-F1 = %.3f (gate %s)' % (r['macro_f1'], '$MIN_F1'))"
  done
} >&2
tar -cf - clean_stats.json report_*.json

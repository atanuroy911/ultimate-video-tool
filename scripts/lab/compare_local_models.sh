#!/usr/bin/env bash
# Make the same videos with each local AI model as the director, on the server installed on this PC, through the normal settings route.
#   bash scripts/lab/compare_local_models.sh "gemma3:4b gemma4:e2b gemma4:e4b qwen3.5:4b" "explainer-watch,story-lighthouse,stick-monday,explainer-bn-payment"
# One folder per model: E:/UltimateVideoTool/matrix/<date>-local-<model>/. The model setting is put back to automatic at the end.
set -u
models="${1:-gemma3:4b gemma4:e2b gemma4:e4b qwen3.5:4b}"
rows="${2:-explainer-watch,story-lighthouse,stick-monday,explainer-bn-payment}"
api="${VT_API:-http://127.0.0.1:8790}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
day="$(date +%Y-%m-%d)"
for m in $models; do
  echo "=== $m"
  curl -s -X PUT "$api/api/settings" -H "Content-Type: application/json" -d "{\"ollama_model\": \"$m\"}" > /dev/null
  "$UV" run --project "$root/server" python "$root/scripts/lab/local_matrix.py" run --director local --rows "$rows" --force \
      --out "E:/UltimateVideoTool/matrix/$day-local-${m//:/-}"
done
curl -s -X PUT "$api/api/settings" -H "Content-Type: application/json" -d '{"ollama_model": ""}' > /dev/null
echo "=== all done"

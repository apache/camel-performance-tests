#!/bin/zsh
# Runs the round-2 stepwise set: every steps-ladder/<name>.json, each from a fresh project, k times.
# Usage: run-stepwise-ladder.sh <tag> [k]      Results: stepwise/<tag>-<i>/<name>/ (results.json, run.log, traces)
# BENCH_REFERENCE=1 applies the reference files instead of asking the model (the reference pass of the steps files).
# BENCH_ONLY=<name> runs one example.
set -u
TAG="${1:?usage: run-stepwise-ladder.sh <tag> [k]}"
K="${2:-1}"
cd "$(dirname "$0")"
export MCP_URL="${MCP_URL:-http://127.0.0.1:9090/mcp}"
command -v caffeinate > /dev/null && caffeinate -i -s -w $$ &
for i in $(seq 1 "$K"); do
  if (( K > 1 )); then T="$TAG-$i"; else T="$TAG"; fi
  : > "stepwise-$T.log"   # a fresh log per run, so a later wait on its DONE line cannot see an earlier run's
  for f in steps-ladder/*.json; do
    name=$(basename "$f" .json)
    if [[ -n "${BENCH_ONLY:-}" && "$name" != "$BENCH_ONLY" ]]; then continue; fi
    python3 gen_stepwise.py "$name" > /dev/null
    echo "[$T] $name start $(date +%T)" | tee -a "stepwise-$T.log"
    BENCH_STEPS="$f" BENCH_TAG="$T/$name" python3 agent_mcp_stepwise.py > "stepwise-$T-$name.out" 2>&1
    tail -1 "stepwise/$T/$name/run.log" | tee -a "stepwise-$T.log"
    # safety net: the harness stops its integration, but an interrupted run leaves one behind
    camel stop "$name" > /dev/null 2>&1 || true
  done
  echo "[$T] DONE $(date +%T)" | tee -a "stepwise-$T.log"
done
python3 summarize_stepwise.py "$TAG" "$K"

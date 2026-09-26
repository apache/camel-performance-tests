#!/bin/zsh
# Runs one full suite: the one-shot examples, then the stepwise edits. Usage: run-suite.sh <tag> [k]
# With k > 1 the suite runs k times as <tag>-1 .. <tag>-k and passk.py reports pass@k and pass^k at the end.
# Results: oneshot-<tag>/, stepwise/<tag>/, <tag>.log (wall clock). Summarise with: summarize_runs.py <tag>
# Environment: BENCH_EXAMPLES=examples-intermediate.json selects set B (services started per example with
# `camel infra`); BENCH_STEPWISE=0 skips the stepwise half (set B has no stepwise project).
set -u
TAG="${1:?usage: run-suite.sh <tag> [k]}"
K="${2:-1}"
cd "$(dirname "$0")"
export MCP_URL="${MCP_URL:-http://127.0.0.1:9090/mcp}"
export BENCH_VALIDATE_PROPS=1
export BENCH_VALIDATE_SOURCE=1
export BENCH_EXAMPLES="${BENCH_EXAMPLES:-examples.json}"
STEPWISE="${BENCH_STEPWISE:-1}"
# the one-shot model gets catalog lookups and validation only: no example catalog (that would hand it the answer), no runtime tools
# the shared authoring tools of the catalog and validation kind; after CAMEL-24712 these are the only catalog tools
export BENCH_TOOL_ALLOW="${BENCH_TOOL_ALLOW:-^camel_(catalog_(doc|find|sample|docs)|validate_source|component_properties|configuration_validate|error_diagnose|eval_expression)$}"
command -v caffeinate > /dev/null && caffeinate -i -s -w $$ &   # macOS: keep the machine awake for the hour
tags=()
for i in $(seq 1 "$K"); do
  if (( K > 1 )); then T="$TAG-$i"; else T="$TAG"; fi
  tags+=("$T")
  echo "[$T] one-shot start $(date +%T) examples=$BENCH_EXAMPLES" | tee -a "$T.log"
  BENCH_OUT="oneshot-$T" python3 agent_local.py > "oneshot-$T.out" 2>&1
  echo "[$T] one-shot done $(date +%T)" | tee -a "$T.log"
  if [[ "$STEPWISE" == "1" ]]; then
    # the stepwise project starts from the timer-log example every time
    git checkout -q -- stepwise-project 2>/dev/null || true
    echo "[$T] stepwise start $(date +%T)" | tee -a "$T.log"
    BENCH_TAG="$T" python3 agent_mcp_stepwise.py > "stepwise-$T.out" 2>&1
    echo "[$T] stepwise done $(date +%T)" | tee -a "$T.log"
    git checkout -q -- stepwise-project 2>/dev/null || true
  fi
  echo "[$T] DONE" | tee -a "$T.log"
done
python3 summarize_runs.py "${tags[@]}"
if (( K > 1 )); then python3 passk.py "${tags[@]}"; fi

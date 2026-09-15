#!/bin/zsh
# Runs one full suite: the one-shot examples, then the stepwise edits. Usage: run-suite.sh <tag>
# Results: oneshot-<tag>/, stepwise/<tag>/, <tag>.log (wall clock). Summarise with: summarize_runs.py <tag>
set -u
TAG="${1:?usage: run-suite.sh <tag>}"
cd "$(dirname "$0")"
export MCP_URL="${MCP_URL:-http://127.0.0.1:9090/mcp}"
export BENCH_VALIDATE_PROPS=1
export BENCH_VALIDATE_SOURCE=1
# the one-shot model gets catalog lookups and validation only: no example catalog (that would hand it the answer), no runtime tools
export BENCH_TOOL_ALLOW="${BENCH_TOOL_ALLOW:-^camel_(catalog_(components|component_doc|eips|eip_doc|languages|language_doc|dataformats|dataformat_doc|docs|doc|find|sample)|validate_(yaml_dsl|route|source)|component_properties|configuration_validate|error_diagnose|eval_expression)$}"
command -v caffeinate > /dev/null && caffeinate -i -s -w $$ &   # macOS: keep the machine awake for the hour
echo "[$TAG] one-shot start $(date +%T)" | tee -a "$TAG.log"
BENCH_OUT="oneshot-$TAG" python3 agent_local.py > "oneshot-$TAG.out" 2>&1
echo "[$TAG] one-shot done $(date +%T)" | tee -a "$TAG.log"
# the stepwise project starts from the timer-log example every time
git checkout -q -- stepwise-project 2>/dev/null || true
echo "[$TAG] stepwise start $(date +%T)" | tee -a "$TAG.log"
BENCH_TAG="$TAG" python3 agent_mcp_stepwise.py > "stepwise-$TAG.out" 2>&1
echo "[$TAG] stepwise done $(date +%T)" | tee -a "$TAG.log"
git checkout -q -- stepwise-project 2>/dev/null || true
echo "[$TAG] DONE" | tee -a "$TAG.log"
python3 summarize_runs.py "$TAG"

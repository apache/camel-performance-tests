# AI benchmark: a local model builds and edits Camel integrations through the Camel MCP server

A small harness that measures how well a model builds and edits Apache Camel integrations when its only Camel
knowledge is what the Camel MCP server (`camel mcp`) gives it: the catalog, validation, and a `camel run` loop.
It was written for the series described in the blog post
[We had a frontier AI coach a small local model through Camel](https://camel.apache.org/blog/2026/09/camel-local-model-benchmark/)
(2026-09-15), where a 22 GB local model went from 0 to 12 of 13 beginner examples over twenty runs while Camel, not
the model, was changed between runs. The results of that series are in [results-2026-09.md](results-2026-09.md).

The harness is here so the next series can be run the same way with a different set of examples, a different model,
or a later Camel, and so anyone, human or agent, can repeat it.

## What it measures

Two benchmarks, both scored by what actually runs, not by reading the model's output:

1. **One-shot** (`agent_local.py`): each example is requested with its one-line description only ("Split a batch of
   items into individual messages for processing"). The model may call the catalog and validation tools, then answers
   with complete files. The harness writes them, validates them with the Camel CLI, runs them with `camel run` for a few
   seconds, and checks the log for the described behaviour. A failure is fed back (validator output, run errors) for up
   to three rounds. Pass means: validates, starts, and shows the expected activity in the log.
2. **Stepwise** (`agent_mcp_stepwise.py`): the model edits a running integration one request at a time ("fire every
   five seconds", "add a choice", "add error handling", eight requests) through the write, run, log and error tools of
   the MCP server. Each step is scored on the file on disk (a regex), the properties file, the log of the running
   integration after the reload, and the errors, against a reference checkpoint.

The model is never shown the example projects or their catalog tools; the one-shot tool set is restricted to catalog
lookups and validation (`BENCH_TOOL_ALLOW` in `run-suite.sh`).

## Prerequisites

- Java 17+ and the Camel CLI (`camel`) on the PATH, the version you want to measure (a locally built snapshot works).
- [Ollama](https://ollama.com) with the model pulled, e.g. `ollama pull qwen3.6:35b-a3b` (any model that supports tool
  calling in Ollama's chat API works; set `BENCH_MODEL`).
- Python 3.10+ (standard library only, no packages).
- macOS or Linux; the scripts are zsh (`run_one.sh`, `start-server.sh`, `run-suite.sh`).

## Running a suite

```bash
cd ai-benchmark
./start-server.sh            # camel mcp --http on port 9090, waits until it answers
./run-suite.sh my-run        # one-shot examples, then the stepwise edits; about 30 to 60 minutes on a laptop
python3 summarize_runs.py my-run   # the markdown table for that run (run-suite.sh prints it too)
```

To compare runs, pass several tags: `python3 summarize_runs.py before after1 after2`.

Environment variables (all optional):

| Variable | Default | Meaning |
|---|---|---|
| `BENCH_MODEL` | `qwen3.6:35b-a3b` | the Ollama model |
| `OLLAMA_HOST` | `http://localhost:11434` | where Ollama listens |
| `MCP_URL` | `http://127.0.0.1:9090/mcp` | the Camel MCP server (Streamable HTTP) |
| `BENCH_ROUNDS` | `3` | one-shot rounds per example |
| `BENCH_TOOL_CALLS` | `10` / `12` | tool calls per round (one-shot) / per step (stepwise) |
| `BENCH_TOOL_ALLOW` | see `run-suite.sh` | regex of the tools offered in the one-shot benchmark |
| `BENCH_OUT` | `oneshot` | one-shot output directory (`run-suite.sh` sets `oneshot-<tag>`) |
| `BENCH_TAG` | model name | stepwise output directory under `stepwise/` (`run-suite.sh` sets the tag) |
| `BENCH_STEPS` | `steps.json` | the stepwise scenario |
| `BENCH_VALIDATE_PROPS`, `BENCH_VALIDATE_SOURCE` | `0` | also run `camel validate properties` and `camel validate source` on the written files (`run-suite.sh` sets both) |
| `CAMEL_MCP_JAR` | unset | run a locally built `camel-jbang-mcp` runner jar instead of the CLI plugin |

## What comes out

- `oneshot-<tag>/<example>/attempt<n>/`: the files the model wrote, `validate.log`, `run.log`, `probe.log`.
- `oneshot-<tag>/<example>/trace.jsonl`: every tool call and answer with timings and token counts; `result.json`: pass,
  rounds, tool calls, seconds, tokens.
- `stepwise/<tag>/step<n>.trace.jsonl`, `step<n>.after.yaml`, `results.json`.
- `<tag>.log`: the wall clock of the suite.

The useful part is the traces. After a run, read every failed attempt: what the model wrote, what the validator said,
what the runtime said. Every message that told the model what was wrong without saying what to write is a Camel
improvement waiting to be made, for a person as much as for the model; that is how the 117 findings of the first series
were found (about 15 minutes of reading per run).

## Changing the examples

- **One-shot:** `examples.json` is a list of `{name, prompt, expect, run_seconds, probe?}`. `prompt` is what the
  model gets, `expect` is for the human reading the results, `run_seconds` how long `camel run` runs, `probe` an
  optional shell command run 7 s after start (for example a `curl` against a REST example) whose output lands in
  `probe.log`. The pass check looks for log activity from the route; adjust `agent_local.py` if an example needs a
  specific check. The first series used the 13 beginner examples of
  [camel-jbang-examples](https://github.com/apache/camel-jbang-examples); a second series should use examples the
  model has not seen, such as the intermediate ones.
- **Stepwise:** `steps.json` names the project directory (`stepwise-project/`, reset to the timer-log example before
  each run), the route and properties files, and the steps, each with a `request`, a `check` (`file_regex`,
  `props_regex`, `log_regex`, `min_log`, `interval_min`, `max_errors`) and a `reference` of the expected files.

## Other conditions

- `gen_local.py`: the bare-prompt condition, no tools at all, output under `local/`. It is what the first series
  measured as "0 of 13" and is the baseline any tool-assisted run should be compared with.
- The frontier condition of the first series was not scripted: a coding agent with the Camel CLI as tools built the same
  examples and scored 13 of 13, with the loop turning 9 first-time passes into 13.

## Notes for an agent running this

- Do not run Maven and the suite at the same time, and do not rebuild `camel-jbang-mcp` while a run is in progress:
  the server loads its jar lazily and a replaced jar breaks it mid-run. Restart the server after a rebuild.
- A `camel.main.durationMaxSeconds` in a generated `application.properties` overrides `--max-seconds`; `run_one.sh` has
  a watchdog for that.
- A model call that takes more than ten minutes is the machine asleep, not the model; `summarize_runs.py` subtracts
  those, and `run-suite.sh` runs `caffeinate` on macOS.
- Keep the examples away from the model: never offer `camel_catalog_examples` or `camel_catalog_example_file` in
  `BENCH_TOOL_ALLOW` for a benchmark that uses the examples repository.

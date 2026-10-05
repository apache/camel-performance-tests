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
   integration after the reload, and the errors, against a reference checkpoint. Since round 2 the stepwise benchmark
   runs over a ladder of examples, one steps file each; see [The stepwise ladder](#the-stepwise-ladder).

The model is never shown the example projects or their catalog tools; the one-shot tool set is restricted to catalog
lookups and validation (`BENCH_TOOL_ALLOW` in `run-suite.sh`): the shared `camel_catalog_doc`, `camel_catalog_find`,
`camel_catalog_sample`, `camel_validate_source` and a few smaller ones. The first series also offered the older per-kind
catalog tools that CAMEL-24712 removes; the allow-list here names the shared ones only.

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

## Round 2: k runs, a held-out set, services

Added 2026-09-17 for the second series.

- `run-suite.sh <tag> <k>` runs the suite k times as `<tag>-1 .. <tag>-k` and ends with `passk.py`, which prints
  per-example passes out of k, **pass@k** (passed at least once) and **pass^k** (passed every time), the two
  consistency measures of the MuleSoft integration-skill post so the series can be compared with it.
- `BENCH_EXAMPLES=examples-intermediate.json BENCH_STEPWISE=0 run-suite.sh b 3` runs set B: six intermediate examples
  the model has never been tested on (openapi-server, openapi-client, sql, artemis, mqtt, route-topology).
  Each entry may declare, all visible in the JSON rather than hidden in the harness:
  - `infra`: services started with `camel infra run <svc> --background` before the example and stopped after it
    (postgres, artemis, mosquitto, kafka); the connection data from `camel infra get <svc> --json` is appended
    to the prompt, as a developer would read it from the same command. Postgres needs about 80 s to come up.
  - `seed`: files under `seed/<example>/` copied into every attempt folder before the model's files (the petstore
    OpenAPI spec and sample payloads); the prompt lists them and says not to rewrite them.
  - `hint`: one extra sentence in the prompt (the MQTT topic, the petstore base path).
  - `pre` / `post`: shell commands run in this directory around the example (openapi-client starts the reference
    petstore server from `seed/openapi-server-ref/` and stops it after).
- Docker Desktop must be running for `infra`; `camel infra` pulls the images on first use.

## The stepwise ladder

Added in round 2 (2026-09-19 onwards); the main benchmark since 2026-09-21, because building an integration one
request at a time is how people work with Camel, and the one-shot prompt is not.

Each rung of the [camel-jbang-examples](https://github.com/apache/camel-jbang-examples) ladder that runs without
Docker (plus the sql rung, with `camel infra`) is one stepwise scenario, written from its README's "Build it step by
step" section: the README's step 1 is the starting project, and each
later step is one request to the model. The model edits the running integration through the MCP server; the harness
scores each step before sending the next.

```bash
./start-server.sh                       # set CAMEL_MCP_JAR to measure a locally built camel-jbang-mcp
python3 gen_stepwise.py                 # writes steps-ladder/<name>.json and stepwise-ladder/<name>/ for every example
BENCH_REFERENCE=1 ./run-stepwise-ladder.sh ref       # the reference pass: must pass every step before a model run
./run-stepwise-ladder.sh s1 5           # five runs: stepwise/s1-1 .. s1-5, then the summary table
./run-http.sh h1 3                      # only the four HTTP rungs: stock-api, http-client, openapi-server/-client
BENCH_ONLY="transform-xslt route-aggregator" ./run-stepwise-ladder.sh x 1   # any subset, names as in steps-ladder/
python3 summarize_stepwise.py s1 5      # the summary again: passes per example and step, runs with every step passed
```

A full ladder run of the 21 examples takes about 65 minutes on the Mac mini the series runs on (qwen3.6:35b-a3b in
Ollama); the four HTTP rungs about 13. Every JSON
file in `steps-ladder/` is run, so keep hand-made scenario files out of it.

### Where the steps come from

`gen_stepwise.py` holds the definitions: for each example the starting files (`initial`), the steps (`request`,
`check`, `reference`) and the settings below. `steps-ladder/` and `stepwise-ladder/` are generated (git ignores them),
so change a step in `gen_stepwise.py` and never in the JSON. The runner calls `gen_stepwise.py <name>` before every
pass, which rewrites that example's steps file and resets its project, so each pass starts from the same files.

- `seed`: files under `seed/<name>/` copied into the project (data files such as `stock.json`, `orders/`, a contract);
  `exclude_seeds` leaves out a file the model is asked to write (`packing-slip.xsl`).
- `peer`: a second app the example talks to, started with `camel run --source-dir` before the model's app and stopped
  after it. `contracts-openapi-client` calls the stock API in `seed/_peer-openapi-server` on port 8080.
- `infra`: services started with `camel infra run` (the sql rung's Postgres); they stay up across the passes of a run
  and are stopped when the run is over. Docker must be running.
- `restart`: on a step that adds or changes Java, the harness restarts the app after the model's turn, as the README's
  step says; a reload does not compile a class.
- `wait_seconds`: how long to wait after the reload before the log and files are checked.

### What a step is scored on

`ok` means `file_ok`, `props_ok` and `log_ok` all hold and the step logged no new errors (`ok_final` is the same
without the errors condition; the summary reports it as "final state right", since a model that tests its own app
with the HTTP request tool causes errors on the way to a right answer, which `ok` counts against it). The checks, all
optional:

| Check | Passes when |
|---|---|
| `file_regex`, `file_regex2` | the route file matches (both, if both are given) |
| `file_not_regex` | the route file does not match |
| `props_regex` | `application.properties` matches |
| `files` | `{name: regex}`: another project file matches; found by name anywhere in the project if not at that path |
| `log_regex` | a regex or a list of them; every one matches an INFO or WARN record (`min_log` times, default 1) |
| `log_not_regex` | no record logged after this step's reload matches |
| `interval_min` | the first two records matching `log_regex` are at least this many seconds apart |
| `probes` | HTTP requests (`method`, `url`, `headers`, `body`, `expect_status`, `body_regex`) sent after the reload; each is retried up to six times, two seconds apart, until status and body match, since the old route may still answer during a reload |
| `errors_ok` | errors in the log do not fail the step (a step that provokes failures on purpose) |
| `min_errors` | at least this many errors must be logged |

Errors are counted per step: ERROR records in the log and entries from `camel_get_errors` that were not there before
the step.

### Tools and model settings

The model gets the shared authoring tools (`SHARED` in `agent_mcp_stepwise.py`: catalog doc/find/sample, validate,
get/write/edit file, run, control, log, errors, eval expression, error diagnose) plus `camel_catalog_docs`,
`camel_component_properties` and `camel_configuration_validate`, and at most 20 tool calls per step
(`BENCH_TOOL_CALLS`), in a 64k context (`BENCH_NUM_CTX`; at 32k the longer examples ran out of context by their last
step and the model stopped without a tool call). `camel_edit_file` is in the set because a model that rewrites a whole
file to change one line corrupts lines it was not asked to touch. `BENCH_EXTRA_TOOLS` adds tools for an experiment
(the SQL tool group of CAMEL-24834).

The harness sends `think: false` to Ollama. With thinking on, the HTTP series s5 lost 4 of 33 steps to thinking
spirals of 4 to 8 minutes and 12k to 28k tokens that ended without an answer.

### What comes out

`stepwise/<tag>/<name>/`: `results.json` (per step: the checks, probe answers, errors with their first lines, tool
calls, refused writes, seconds, tokens, the model's closing answer), `run.log` (one line per step), `step<n>.trace.jsonl`
(every model turn and tool call), `step<n>.after.yaml` (the route file after the step), `camel-run.out` and
`peer-run.out` (the apps' console). `stepwise-<tag>.log` has one line per example.

### Pitfalls

- Never write a log or output file inside a project the app watches (`--source-dir`): every write reloads the app,
  and a reload that logs writes again. Output belongs under `stepwise/`, which is outside the projects.
- Run the reference pass after any change to `gen_stepwise.py`, a seed, or Camel: a reference that fails is a
  harness or Camel bug, not a model result.
- Do not share one MCP server between two runs, a reference pass included: the step logs and error counts of one get
  mixed into the other.

# Results of the third series, 2026-10-02 to 2026-10-05 (so far)

Round 3 started from a clean slate on the Camel main branch of 2026-10-02 (b223a80dd6e1), with the same local model
(`qwen3.6:35b-a3b` via Ollama on an Apple M4 Pro, 64 GB) and the stepwise ladder of round 2 (21 examples, 71 steps,
20 tool calls per step). A full-ladder baseline was run, the failures were read, and small series on one or two
examples measured each change before it was merged. A second baseline on 2026-10-04 (main 6589e123eb0f, every fix
of the weekend merged) closes this part; the notes call it round 4. Everything measured here is in Camel 4.23.

## The two baselines

| | r3 (10-02/03) | r4 (10-04/05) |
|---|---|---|
| Camel main | b223a80dd6e1 | 6589e123eb0f |
| Context / tool groups | 32k / off | 64k / on |
| Steps passed, strict | 300 of 355 (84.5%) | 307 of 355 (86.5%) |
| Steps passed, final | 307 of 355 (86.5%) | 318 of 355 (89.6%) |
| Clean runs (every step passed) | 55 of 105 | 65 of 105 |
| Examples clean in all 5 runs (pass^5) | 7 of 21 | 8 of 21 |
| The four HTTP rungs, strict / final | 52 / 54 of 65 | 50 / 56 of 65 |

Round 2 ended at 82.7% strict and 85.2% final (s19, scored with the older harness checks).

## What each change did

Small series, k=5, on the examples a change was meant for; the "before" column is the baseline or a control run of
the same build.

| Series | Example(s) | Change | Before | After |
|---|---|---|---|---|
| r3b | 5 examples that ran out of room | 64k context instead of 32k | circuit-breaker 9 of 15 | 13 of 15 |
| r3log | circuit-breaker | `camel_get_log` leaves out stack traces (CAMEL-25296) | 14 of 15 (r3cb) | 14 of 15, peak context 35.8k of 64k |
| r3tg | service-sql, circuit-breaker | tool groups offered by the running app (CAMEL-24834) | 22 of 30 (r3b) | 22 of 30 strict, 24 final |
| r3http2 | the four HTTP rungs | the HTTP tool group (CAMEL-25307) | 51 / 56 of 65 (r3h0) | 50 / 55 of 65 |
| r3pp | openapi-client | client request validation of path parameters (CAMEL-25321) | 9 of 15 (r3pp0) | 11 of 15; requests with a literal `{sku}`: 942 to 0 |
| r4og | order-generator | the validator finds classes under `src/main/java` (CAMEL-25327) | 11 of 20 | 17 of 20 |
| r4eh | error-handling | hint for an error handler written as a step (CAMEL-25328) | 12 of 15 | 11 of 15, inconclusive |
| r4ol | order-lines | step 1 request worded so it cannot be misread (harness) | 12 of 15 | 15 of 15 |
| r4jp | openapi-server | `marshal: json` passes JSON text through (CAMEL-25329) | 12 / 14 of 20 | 14 / 14 of 20; double-encoded answers gone |
| r4m | openapi-server | plus the Groovy "unmarshal it first" hint (CAMEL-25330), the validator's checks for a field read on text (CAMEL-24844) and for `${...}` in a constant (CAMEL-25336) | 12 / 14 of 20 | 18 / 18 of 20 |

Reading the tables:

- The baseline moved from 84.5% to 86.5% strict and from 86.5% to 89.6% final between the two baselines; 10 more
  runs passed every step.
- The biggest single gain was the context: at 32k the circuit-breaker example filled it in every run.
- Not every change paid off in the numbers: the log without stack traces, the tool groups, the HTTP tool group and
  the error-handler hint did not move the score. They were merged for what they do for the model's context and
  messages, not for a measured gain.
- openapi-server step 1 (look up the stock JSON by sku) failed in every run of every series until 2026-10-05; it
  passes 4 of 5 in r4m. The failures were about the body type: JSON still as text where a script read its fields,
  and `${header.sku}` in a constant, which is never evaluated. The validator now says so before the app runs.
- A series is only as good as its build: r4f (not listed) ran while a reactor build replaced the runtime jars, so it
  measured the validator alone. r4m was run again on main with the jar checksums checked at the end.

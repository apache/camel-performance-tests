# Results of the second series, 2026-09-17 to 2026-09-28

Round 2 used the same local model as the first series (`qwen3.6:35b-a3b` via Ollama on an Apple M4 Pro, 64 GB) against
the Camel MCP server. It started as a repeat of round 1, then moved to harder examples: the
[camel-jbang-examples](https://github.com/apache/camel-jbang-examples) ladder. On 2026-09-21 the stepwise benchmark
became the main one: building an integration one request at a time is how people work with Camel, and one-shot
prompting is not. As in round 1, what changed between runs was Camel: every failed attempt was read, and an unclear
message became a hint, a check or a tool before the next series. Everything measured here is in Camel 4.23.

## A week later: the round-1 set, nothing changed (runs 21 to 30)

The 13 one-shot examples and 8 stepwise edits of round 1, ten times, on main of 2026-09-17 (d92534888ba4), to see how
stable the result is.

| | run21 | run22 | run23 | run24 | run25 | run26 | run27 | run28 | run29 | run30 |
|---|---|---|---|---|---|---|---|---|---|---|
| One-shot passes | 13 of 13 | 13 of 13 | 10 of 13 | 12 of 13 | 12 of 13 | 13 of 13 | 13 of 13 | 13 of 13 | 12 of 13 | 13 of 13 |
| One-shot first-round passes | 5 | 8 | 5 | 7 | 7 | 5 | 7 | 5 | 9 | 8 |
| One-shot rounds / tool calls | 22 / 74 | 19 / 79 | 24 / 77 | 21 / 70 | 21 / 82 | 25 / 75 | 20 / 74 | 22 / 76 | 18 / 79 | 21 / 67 |
| One-shot tokens | 94,971 | 47,241 | 87,445 | 36,729 | 49,789 | 83,263 | 71,612 | 66,164 | 35,851 | 64,757 |
| Stepwise passes (strict / lenient) | 7 / 8 of 8 | 8 / 8 of 8 | 8 / 8 of 8 | 8 / 8 of 8 | 8 / 8 of 8 | 8 / 8 of 8 | 7 / 7 of 8 | 8 / 8 of 8 | 8 / 8 of 8 | 8 / 8 of 8 |
| Stepwise tool calls / refused writes | 21 / 2 | 28 / 4 | 31 / 4 | 20 / 3 | 17 / 4 | 18 / 3 | 21 / 3 | 22 / 4 | 23 / 2 | 19 / 2 |
| Stepwise tokens | 9,460 | 9,372 | 14,609 | 9,619 | 9,959 | 9,420 | 12,137 | 12,891 | 9,004 | 10,754 |
| Suite wall clock (sleep stalls removed) | 39 min (33 + 5) | 26 min (20 + 6) | 38 min (31 + 7) | 22 min (16 + 5) | 26 min (20 + 5) | 36 min (30 + 5) | 32 min (25 + 6) | 31 min (25 + 6) | 21 min (15 + 5) | 30 min (24 + 6) |
| One-shot failures | none | none | groovy, xslt, message-size | message-size | groovy | none | none | none | routes | none |
| Stepwise failures | 2 | none | none | none | none | none | 4 | none | none | none |

pass@10 is 13 of 13 and pass^10 9 of 13: every example passed at least once, and 9 passed in all ten runs. The two
stepwise misses were harness checks, not the model.

## One-shot on the ladder (2026-09-19 to 2026-09-21)

The examples of the ladder, each prompted with its one-line description, thinking off, on main as it changed.

| Series | Examples | k | Passes | pass@k | pass^k |
|---|---|---|---|---|---|
| l (09-19) | 20 | 3 | 5, 6, 7 of 20 | 9 of 20 | 3 of 20 |
| l2 (09-20) | 20 | 3 | 8, 7, 5 of 20 | 10 of 20 | 4 of 20 |
| l3 (09-20) | the 10 that had passed once | 5 | 5, 9, 7, 7, 5 of 10 | 9 of 10 | 4 of 10 |
| l4 (09-21) | the same 10 | 5 | 6, 9, 5, 8, 7 of 10 | 10 of 10 | 4 of 10 |

## The stepwise ladder (2026-09-21 to 2026-09-28)

Each rung of the ladder is one scenario: the README's step 1 is the starting project, each later step one request to
the model. A step is strict-correct when the file, properties and log checks hold and no new error was logged;
"final" drops the error condition, since a model that tests its own app logs errors on the way to a right answer.
A clean run is a run of one example with every step passed.

| Series | Examples | k | Tool calls per step | Strict | Final | Clean runs |
|---|---|---|---|---|---|---|
| s1 (09-21) | 10 | 5 | 12 | 142 of 170 (83.5%) | – | 29 of 50 |
| s2 (09-21) | 10 | 5 | 12 | 139 of 170 (81.8%) | 139 of 170 | 29 of 50 |
| s3 (09-21) | 11 | 5 | 12 | 162 of 185 (87.6%) | 165 of 185 | 41 of 55 |
| s16 (09-24) | 21 | 5 | 12 | 270 of 355 (76.1%) | 275 of 355 | 46 of 105 |
| s17 (09-25) | 21 | 10 | 12 | 545 of 709 (76.9%) | 556 of 709 | 99 of 210 |
| s18 (09-26) | 21 | 10 | 12 | 569 of 710 (80.1%) | 584 of 710 | 106 of 210 |
| s19 (09-27) | 21 | 10 | 20 | 587 of 710 (82.7%) | 605 of 710 (85.2%) | 117 of 210 |

The four HTTP rungs (stock-api, http-client, openapi-server, openapi-client) were the hardest part, and got their
own series while the fixes for them were made:

| Series | s5 | s11 | s12 | s13 | s14 | s15 |
|---|---|---|---|---|---|---|
| Steps passed (strict) | 14 of 39 | 28 of 65 | 32 of 65 | 29 of 65 | 36 of 65 | 43 of 65 |

Reading the tables:

- One-shot is stable on the round-1 set (124 of 130 passes in ten runs) but weak on the ladder: about a third of the 20
  examples per run (l, l2). Stepwise, the same ladder passes about 80% of its steps. One request at a time suits a local model.
- s1 to s3 used the first 10 and 11 rungs; from s16 the full ladder of 21, which is why the percentage drops there.
  On the full ladder strict went from 76% (s16) to 83% (s19).
- s19 gave the model 20 tool calls per step instead of 12: with 12, 115 of 720 steps ran out of calls in s18.
- The HTTP rungs went from 14 of 39 (36%, s5) to 43 of 65 (66%, s15). The fixes that moved them include the
  `camel_edit_file` tool (CAMEL-24909), hints that print the line to write (CAMEL-24906), a failed reload keeping the
  last good version (CAMEL-24899), and the check of where the body comes from across the routes of a file
  (CAMEL-24844).
- s16 to s19 were scored before the harness fixes of 2026-09-29 (a wider log window, a check that accepted only one
  correct spelling), so they understate the model a little.

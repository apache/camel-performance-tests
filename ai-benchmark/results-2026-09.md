# Results of the first series, 2026-09-12 to 2026-09-13

Twenty runs of the same 13 one-shot examples and 8 stepwise edits with the same local model (`qwen3.6:35b-a3b` via Ollama
on an Apple M4 Pro, 64 GB), against the Camel MCP server. What changed between runs was Camel: after each run every failed
attempt was read, the unclear message became a hint or a check, and the fix was merged before the next run. The story is
in the blog post: https://camel.apache.org/blog/2026/09/camel-local-model-benchmark/

Column "before" is the Camel main branch of 2026-09-12 with the shared authoring tools (CAMEL-24695) only. Runs 1 to 20
add the fixes as they were made; run 2 was stopped and is not listed. Everything measured here is in Camel 4.23.

| | before | run1 | run3 | run4 | run5 | run6 | run7 | run8 | run9 | run10 | run11 | run12 | run13 | run14 | run15 | run16 | run17 | run18 | run19 | run20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| One-shot passes of 13 | 10 | 7 | 10 | 10 | 9 | 10 | 8 | 10 | 13 | 10 | 9 | 11 | 10 | 10 | 10 | 10 | 11 | 10 | 12 | 12 |
| One-shot first-round passes | 5 | 1 | 2 | 5 | 4 | 4 | 4 | 4 | 3 | 2 | 4 | 3 | 4 | 5 | 5 | 4 | 5 | 5 | 9 | 7 |
| One-shot rounds / tool calls | 28 / 84 | 33 / 82 | 29 / 79 | 26 / 70 | 28 / 51 | 28 / 70 | 28 / 58 | 29 / 83 | 26 / 71 | 32 / 65 | 27 / 74 | 28 / 70 | 26 / 65 | 24 / 60 | 25 / 53 | 25 / 59 | 24 / 66 | 24 / 60 | 19 / 50 | 21 / 52 |
| One-shot tokens | 169,596 | 103,908 | 63,030 | 75,355 | 72,695 | 110,119 | 83,348 | 132,131 | 42,482 | 80,185 | 81,556 | 106,498 | 52,370 | 104,892 | 53,839 | 52,828 | 47,067 | 97,521 | 60,105 | 61,173 |
| Stepwise passes of 8 (strict / lenient) | 5 / 5 | 5 / 6 | 8 / 8 | 7 / 8 | 8 / 8 | 7 / 8 | 8 / 8 | 7 / 7 | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 | 7 / 7 | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 | 8 / 8 | 7 / 8 |
| Stepwise tool calls / refused writes | 34 / 9 | 34 / 11 | 31 / 2 | 20 / 2 | 31 / 4 | 24 / 3 | 21 / 2 | 27 / 4 | 22 / 2 | 19 / 3 | 40 / 9 | 30 / 4 | 22 / 3 | 15 / 2 | 19 / 2 | 23 / 2 | 19 / 2 | 26 / 2 | 20 / 2 | 24 / 2 |
| Stepwise tokens | 41,264 | 19,773 | 7,896 | 6,567 | 9,975 | 10,778 | 9,901 | 11,390 | 8,201 | 12,843 | 15,424 | 11,421 | 8,755 | 9,277 | 6,370 | 7,802 | 9,365 | 11,834 | 7,629 | 9,975 |
| Suite wall clock (sleep stalls removed) | 72 min (56 + 16) | 45 min (36 + 9) | 31 min (25 + 6) | 33 min (28 + 4) | 35 min (28 + 6) | 45 min (39 + 6) | 38 min (31 + 6) | 52 min (46 + 6), 47 min asleep | 116 min (110 + 5), 46 min asleep | 39 min (33 + 6) | 38 min (29 + 8) | 44 min (37 + 6) | 29 min (24 + 5) | 42 min (37 + 5) | 27 min (22 + 4) | 27 min (22 + 5) | 25 min (20 + 5) | 41 min (34 + 6) | 28 min (23 + 5) | 29 min (23 + 6) |
| One-shot failures | rest-api, aggregator, memory-leak | rest-api, routes, tui-hello-world, aggregator, circuit-breaker, groovy | content-based-router, aggregator, memory-leak | aggregator, xslt, memory-leak | splitter, aggregator, xslt, message-size | routes, groovy, memory-leak | routes, splitter, aggregator, groovy, memory-leak | circuit-breaker, xslt, memory-leak | none | routes, groovy, xslt | routes, aggregator, xslt, message-size | xslt, memory-leak | content-based-router, aggregator, memory-leak | routes, xslt, memory-leak | routes, groovy, memory-leak | routes, content-based-router, memory-leak | aggregator, groovy | routes, content-based-router, memory-leak | memory-leak | xslt |
| Stepwise failures | 6, 7, 8 | 2, 4, 6 | none | 2 | none | 2 | none | 7 | none | none | none | none | 4 | none | none | none | none | none | none | 2 |

Reading the table:

- One-shot passes went from 7 (strict) to 12 of 13; first-round passes from 5 to 9 (run 19); tokens from 170k to about 60k.
- The stepwise edits reached 8 of 8 from run 3 on and stayed there.
- From run 14 the remaining one-shot failures were the model's (thinking spirals of 20k to 27k tokens, answering with
  pasted files instead of the write tool after a correct hint), not Camel's; the series stopped at run 20 for that reason.
- The wall clock removes the time the laptop was asleep (a model call longer than 600 s); `caffeinate` in `run-suite.sh`
  keeps it awake now.

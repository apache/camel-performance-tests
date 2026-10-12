# camel-groovy performance review

_Claude Code on behalf of Croway_

> All numbers come from full runs: JMH with 2 forks × 5 × 2 s warmup and measurement unless a section says otherwise,
> and 5-minute load runs compared over 60–300 s. Single-fork profiling runs are labelled as such. Everything was
> measured on one laptop on 2026-09-10. The benchmark branch (camel-performance-tests `camel-groovy-perf`) and the
> camel-groovy prototype (apache/camel `camel-groovy-perf-review`) are local and not pushed, and no JIRA issue has
> been filed.

## 1. Scope

| | |
|---|---|
| Camel | `apache/camel` `main`, 4.23.0-SNAPSHOT, built locally. Java/groovy load runs (13:25–14:26): `364a17a0f752`. Everything after 15:00, including the 19:37–19:47 load re-runs: `e1d8cc6fee92` (23 commits later). Between the two, the only change in the modules under test is CAMEL-24669 (`b0857cd2fc4d`, groovyJson/groovyXml); core, `GroovyExpression`, `GroovyLanguage`, jactl, joor, mvel, javascript, python3 and all their dependency versions are identical. The prototype runs (section 9) replace only the camel-groovy jar (`4.23.0-perf-SNAPSHOT`, built from `565c7f6d95d4` on top of `364a17a0f752`, so without CAMEL-24669; none of the prototype benchmarks uses the data formats) |
| Groovy | **5.1.2** (`groovy-version` on `main` is already 5.1.2, not 5.1.1) |
| Module | `components/camel-groovy` (language, pre-compiled sources, `groovyJson`, `groovyXml`) |
| Also compared | `jactl` (Jactl 2.9.2, Preview), `java` (jOOR), `mvel` (2.5.3), `js` (GraalJS 25.2.4), `python3` (GraalPy 25.2.4) — same logic in every scenario; `ognl` (deprecated) and `python` (Jython 2.7) not included |
| apache/camel#26260 (CAMEL-24669) | not in the 13:25–14:26 load runs (which do not use the data formats); merged in `e1d8cc6fee92`, so included in all JMH runs, see §8 |

## 2. Environment

| | |
|---|---|
| CPU | Apple M1 Pro, 10 cores (8 performance + 2 efficiency), 32 GB, on AC power |
| OS | macOS 26.6.2 (arm64) |
| JDKs | Corretto 17.0.18, Temurin 21.0.10 (primary), Temurin 25.0.2; G1 (default) |
| JMH | 1.37 (latest release) |
| async-profiler | 4.5 (CPU sampling on macOS uses itimer) |
| JMH forks | `-Xms2g -Xmx2g` |
| Load tests | `-Xms1g -Xmx1g`, GC log, JFR `profile` settings |

A laptop is not a server: expect a few percent of noise, and the 8-thread results share 8 performance cores with the
JIT, GC and the JMH harness.

## 3. Method

- JMH benchmarks in `tests/camel-jmh` (`org.apache.camel.itest.jmh.groovy`), 2 forks, 5 × 2 s warmup, 5 × 2 s
  measurement, `Throughput` + `AverageTime` (data formats `AverageTime`), `-prof gc` for bytes/op, `SampleTime` for
  route p99.
- Every benchmark checks once in `@Setup` that all variants return the same result.
- Flamegraphs with async-profiler through JMH (`cpu`, `alloc`, and `lock` for the 8-thread route).
- A long running high load test (`GroovyLoadTest`): 8 producer threads, 5 minutes per variant (the first java /
  groovy / groovyPrototype / groovyManyScripts / fixed-rate runs lasted 10 minutes and are compared over 60–300 s),
  sampling heap, allocation, latency, Metaspace and class loading every 5 s; GC pauses and heap after GC are taken
  from the GC logs (`gc_log_tables.py`). JFR (`settings=profile`) and `-Xlog:gc*,safepoint` are on in every load run,
  equally for all variants.
- A deterministic harness (`GroovyScriptCacheChurnTest`) counting script recompilations.
- All languages share one test classpath. Every JMH benchmark runs in its own forked JVM and only the benchmarked
  language runs in the measured loop, so steady-state numbers are not affected. `@Setup` evaluates every variant once
  (equal-work check), which adds a few receiver types to shared Camel call sites before warmup; not measured, expected
  to be negligible. CamelContext startup and the absolute Metaspace of the load runs include type converters and
  classes discovered from all camel-* jars.
- jactl and python3 need `createWithHostAccess()` to call getters on the POJO body (collection and load scenarios);
  js runs with `HostAccess.ALL` (the camel-javascript default).

See `README.md` for the exact commands.

## 4. Results per scenario

### Scenarios 1 and 2: expression and predicate (JDK 21, `GroovyExpressionTest-jdk21.jmh.json`)

Throughput, 2 forks × 5 × 2 s, error = 99.9% confidence half-width, bytes/op from `-prof gc`, one exchange reused per
thread (so this is the cost of `evaluate` / `matches` only). "vs Java" is the slowdown against the Java `Expression` /
`Predicate` of the same scenario.

| variant | concat (body + '-' + header) | vs Java | bytes/op | arithmetic (body * 2 + 1) | vs Java | bytes/op | predicate (header > 100) | vs Java | bytes/op |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Java `Expression` / `Predicate` | 47,780,724 ± 536,770 | 1.00× | 56 | 434,267,392 ± 3,237,999 | 1.00× | 0 | 279,871,699 ± 1,714,108 | 1.00× | 0 |
| Java `Processor` | 43,844,347 ± 231,094 | 1.09× | 56 | | | | | | |
| java (jOOR) | 44,348,419 ± 317,402 | 1.08× | 56 | 363,446,576 ± 1,332,548 | 1.19× | 0 | 247,313,303 ± 1,487,478 | 1.13× | 0 |
| jactl | 35,389,546 ± 259,800 | 1.35× | 136 | 86,218,393 ± 634,674 | 5.04× | 56 | 73,565,987 ± 421,084 | 3.80× | 56 |
| mvel | 19,034,062 ± 184,871 | 2.51× | 248 | 54,211,377 ± 482,690 | 8.01× | 32 | 65,026,418 ± 889,865 | 4.30× | 32 |
| simple | 13,086,610 ± 167,523 | 3.65× | 352 | 2,916,484 ± 40,484 | 148.9× | 1,676 | 31,089,329 ± 197,310 | 9.00× | 0 |
| **groovy** | **3,001,362 ± 33,509** | **15.9×** | **1,568** | **3,656,819 ± 86,337** | **118.8×** | **1,336** | **3,623,062 ± 23,970** | **77.3×** | **1,344** |
| js (GraalJS, `Interpreted`, new `Context` per evaluation) | 3,120 ± 116 | 15,315× | 862,843 | 3,126 ± 152 | 138,934× | 851,931 | 3,176 ± 91 | 88,127× | 859,438 |
| python3 (GraalPy, `Interpreted`, new `Context` per evaluation) | 115 ± 7 | 415,494× | 5,499,461 | 106 ± 7 | 4,078,677× | 5,225,907 | 118 ± 7 | 2,377,038× | 5,494,383 |

Reading the table:

- **groovy costs ~270–330 ns per evaluation whatever the script** (3.0–3.7 M ops/s for concat, arithmetic and
  predicate alike) and allocates ~1.3–1.6 KB. The script body is not the cost; the per-evaluation work around it is
  (registry lookup, binding maps, reflective `Script` instance — see §7 and scenario 6).
- **java (jOOR)** is within 8–19% of hand-written Java: it compiles to a real method and passes the exchange directly.
  **jactl** and **mvel** add 56–250 bytes and a few ns to tens of ns. **simple** is between them and groovy; its
  arithmetic uses the `sum()` function (1.7 KB per evaluation), not an operator.
- **js and python3** measure the camel-javascript / camel-python3 integration, not the languages: every evaluation
  builds a polyglot `Context` (~0.3 ms / ~9 ms here) and the Graal engine runs `Interpreted` on this stock JDK.
- These are isolated evaluations. A route adds exchange creation and routing around them, so route-level differences
  are smaller (scenario 4).

### Scenario 3: collection logic, "any line item > 100" (JDK 21, `GroovyCollectionTest-jdk21.jmh.json`)

Only the last item matches, so every variant visits every item. jactl and python3 use `createWithHostAccess()` to call
the POJO getters. Throughput (ops/s ± 99.9% error) and bytes per evaluation.

| variant | 10 items | vs Java streams | bytes/op | 1000 items | vs Java streams | bytes/op |
|---|---:|---:|---:|---:|---:|---:|
| Java streams | 11,709,817 ± 1,365,752 | 1.00× | 112 | 184,777 ± 54,517 | 1.00× | 160 |
| java (jOOR) | 12,489,977 ± 86,006 | 0.94× | 112 | 218,515 ± 2,716 | 0.85× | 160 |
| jactl (host access) | 11,389,269 ± 191,643 | 1.03× | 72 | 158,808 ± 1,715 | 1.16× | 96 |
| mvel (`($ in … if $.value > 100).size() > 0`) | 6,190,678 ± 53,426 | 1.89× | 376 | 85,307 ± 770 | 2.17× | 4,336 |
| groovy dynamic | 1,722,843 ± 10,232 | 6.80× | 2,528 | 16,831 ± 535 | 10.98× | 73,849 |
| groovy `@CompileStatic` (via `GroovyShellFactory`) | 1,513,159 ± 22,879 | 7.74× | 3,024 | 17,196 ± 360 | 10.75× | 74,305 |
| pre-compiled Groovy class, dynamic, called directly | 1,991,767 ± 744,533 | 5.88× | 1,180 | 16,169 ± 1,201 | 11.43× | 72,465 |
| pre-compiled Groovy class, `@CompileStatic`, called directly | 2,688,331 ± 299,633 | 4.36× | 1,144 | 16,580 ± 366 | 11.14× | 72,449 |
| pre-compiled Groovy class, dynamic, via `bean` language | 2,100,661 ± 21,981 | 5.57× | 2,484 | 16,704 ± 373 | 11.06× | 73,761 |
| pre-compiled Groovy class, `@CompileStatic`, via `bean` language | 2,054,074 ± 12,745 | 5.70× | 2,464 | 16,532 ± 2,570 | 11.18× | 73,745 |
| js (GraalJS, `Interpreted`, new `Context` per evaluation) | 3,042 ± 96 | 3,849× | 877,118 | 1,417 ± 39 | 130× | 1,479,511 |
| python3 (GraalPy host access, `Interpreted`, new `Context` per evaluation) | 119 ± 6 | 98,188× | 5,510,096 | 104 ± 4 | 1,784× | 6,577,729 |

Reading the table:

- **Noise:** the Java streams baseline has wide error bars (±12% at 10 items, ±29% at 1000; a browser tab used ~80% of
  one core during part of this run). Ratios near 1× (java/jOOR, jactl) are within noise; the groovy, mvel, js and
  python3 gaps are far outside it.
- **Every Groovy variant costs ~72–74 KB per evaluation at 1000 items and runs ~11× slower than Java**, whether
  dynamic, `@CompileStatic`, pre-compiled, called directly or through the `bean` language. The per-element closure call
  of `any {}` dominates (finding 6); static compilation and pre-compilation do not change it. At 10 items the fixed
  per-evaluation overhead still shows. The pre-compiled classes called directly allocate ~1.1–1.2 KB, against
  2.5–3.0 KB through the `groovy` or `bean` language.
- **Pre-compiled classes called directly, 10 items: each JVM fork settles on a different speed, so these two rows
  cannot be ranked.** Two back-to-back repeats with the same code (groovy6 phase, `-groovy-5.1.2`) give six forks
  per benchmark. Within a fork the iterations vary by less than 2%, but the forks land on different levels:
  - dynamic, called directly: 2.46 / 1.52, 1.45 / 2.44, 1.51 / 1.47 M ops/s
  - `@CompileStatic`, called directly: 2.51 / 2.87, 2.96 / 2.46, 1.97 / 2.62 M ops/s

  Each two-fork average above is two samples from those levels, hence the ±37% and ±11%. In the same repeats, groovy
  dynamic and `@CompileStatic` through the language stay within 1.70–1.73 M and 1.50–1.51 M ops/s in every fork, and
  the `bean` variants keep ±1% error bars. The earlier reading that "pre-compiled `@CompileStatic` called directly is
  the fastest groovy variant" is not supported: it is fastest in some forks and not in others. Which JIT decision
  splits the forks was not investigated. Ranking these two rows would need many more forks. They call the Groovy
  class without Camel, so they are outside the end-to-end comparison.
- **jactl and java (jOOR)** stay at Java speed with almost no allocation; **mvel**'s projection allocates a list
  (4.3 KB at 1000 items) and is ~2× Java.
- **js / python3** are dominated by creating a polyglot `Context` per evaluation; at 1000 items the per-item host calls
  add to it.

### Scenario 4: full route, end to end (JDK 21, `GroovyRouteTest-jdk21.jmh.json`)

`direct → filter(amount > 100) → setBody(body + '-' + foo) → counting processor`, sent with
`ProducerTemplate.sendBodyAndHeaders` (a new exchange per message, the filter passes). Throughput in messages per
second ± 99.9% error, bytes allocated per message; "scaling" = 8-thread / 1-thread throughput. OrbStack used about
27% of one core during part of the 8-thread runs (quit at 16:49); java's 8-thread error bar is ±11%.

| route written in | 1 thread msg/s | vs Java | 8 threads msg/s | vs Java | scaling | bytes/msg |
|---|---:|---:|---:|---:|---:|---:|
| Java (lambdas) | 1,352,257 ± 9,711 | 1.00× | 6,321,578 ± 668,119 | 1.00× | 4.7× | 1,560 |
| java (jOOR) | 1,378,663 ± 17,810 | 0.98× | 6,567,132 ± 340,895 | 0.96× | 4.8× | 1,560 |
| jactl | 1,338,124 ± 9,470 | 1.01× | 6,256,786 ± 397,590 | 1.01× | 4.7× | 1,696 |
| mvel | 1,246,366 ± 25,547 | 1.08× | 6,202,373 ± 111,185 | 1.02× | 5.0× | 1,784 |
| simple | 1,201,081 ± 35,625 | 1.13× | 5,626,434 ± 439,314 | 1.12× | 4.7× | 1,856 |
| **groovy** | **652,420 ± 3,466** | **2.07×** | **1,374,665 ± 14,398** | **4.60×** | **2.1×** | **4,664** |
| js (GraalJS, `Interpreted`, new `Context` per evaluation) | 1,567 ± 54 | 863× | 6,135 ± 358 | 1,030× | 3.9× | 1,728,924 |
| python3 (GraalPy, `Interpreted`, new `Context` per evaluation) | 59 ± 2 | 22,859× | 400 ± 20 | 15,787× | 6.8× | 11,000,139 |

Reading the table:

- **End to end, java (jOOR), jactl, mvel and simple are within 0–13% of a Java route** and scale the same way to 8
  threads; the ratios below ~1.1× are inside or close to the error bars.
- **groovy is 2.1× slower than Java on one thread and 4.6× slower on 8 threads**: it only scales 2.1× where every other
  JVM-compiled option scales ~4.7×. That is the `DefaultRegistry` `Stack` monitor that every groovy evaluation takes
  (finding 1), now visible end to end. It allocates 3× the bytes of a Java route per message.
- **js / python3** remain 3–4 orders of magnitude slower end to end, with 1.7 MB / 11 MB allocated per message
  (a polyglot `Context` per evaluation, Graal running `Interpreted`).

**Latency per message, end to end** (SampleTime, `GroovyRouteTest-jdk21-sample.jmh.json`; mean ± error and p99):

| route written in | 1 thread mean | 1 thread p99 | 8 threads mean | 8 threads p99 |
|---|---:|---:|---:|---:|
| Java (lambdas) | 786 ± 23 ns | 916 ns | 1,472 ± 14 ns | 3,164 ns |
| java (jOOR) | 786 ± 20 ns | 916 ns | 1,306 ± 14 ns | 2,292 ns |
| jactl | 797 ± 24 ns | 875 ns | 1,431 ± 15 ns | 2,372 ns |
| mvel | 829 ± 16 ns | 958 ns | 1,537 ± 14 ns | 3,456 ns |
| simple | 852 ± 15 ns | 917 ns | 1,517 ± 15 ns | 3,000 ns |
| **groovy** | **1,667 ± 23 ns** | **1,916 ns** | **6,448 ± 46 ns** | **110,208 ns** |
| js (GraalJS) | 632 ± 1 µs | 782 µs | 1.33 ± 0.003 ms | 2.74 ms |
| python3 (GraalPy) | 16.9 ± 0.15 ms | 25.4 ms | 19.7 ± 0.05 ms | 24.2 ms |

- On one thread groovy adds ~880 ns per message over Java (2.1×), with a tight tail (p99 1.9 µs).
- **With 8 threads groovy's p99 is 110 µs, ~35× Java's 3.2 µs**, while java (jOOR), jactl, mvel and simple stay at
  2.3–3.5 µs. The mean only grows 4.4×: most messages are fast, a minority waits on the `DefaultRegistry` monitor.
  The 10-minute groovy load test shows the same tail (p99 105 µs, §5).

### Scenario 5a: first evaluation of a new script (JDK 21, `GroovyFirstEvaluationTest-jdk21.jmh.json`)

`createExpression` + `init` + first `evaluate` of `body + '-' + header.foo` on a new, started CamelContext (the context
and `resolveLanguage` are untimed). SingleShotTime, 10 forks × 20 iterations, no warmup; every iteration uses a script
text never compiled before. "Cold" is the first iteration of each fork (language runtime not loaded yet in that JVM),
"warm" is iterations 11–20 of the same forks.

| language | cold JVM: median (min–max) | warm JVM: median | warm JVM: p90 |
|---|---:|---:|---:|
| Java lambda (`ExpressionAdapter`) | 0.20 ms (0.19–0.22) | 0.009 ms | 0.013 ms |
| simple | 6.7 ms (6.4–7.4) | 0.145 ms | 0.165 ms |
| mvel | 25.1 ms (24.6–25.8) | 0.38 ms | 0.43 ms |
| jactl | 129 ms (125–131) | 0.90 ms | 1.02 ms |
| js (GraalJS) | 337 ms (333–343) | 3.3 ms | 4.0 ms |
| **groovy** | **376 ms (372–380)** | **4.3 ms** | **5.0 ms** |
| java (jOOR) | 376 ms (371–382) | 65.7 ms | 69.3 ms |
| python3 (GraalPy) | 1,563 ms (1,555–1,595) | 37.6 ms | 47.6 ms |

- **Groovy's first script in a JVM costs ~376 ms** (loading the Groovy compiler and runtime); every further new script
  costs ~4.3 ms to compile (so 1,000 distinct scripts ≈ 4 s of startup compilation). jactl and mvel compile an order
  of magnitude faster; simple is cheapest.
- **java (jOOR)**: 66 ms per script on a warm JVM is inflated in this setup — javac runs annotation processor
  discovery on every compilation and the JMH annotation processor is on the benchmark class path ("Annotation
  processing is enabled because one or more processors were found"). *Suspected, not measured without it.*
- **python3**: each iteration creates a new CamelContext and therefore a new GraalPy `Engine` (the language holds one
  engine), so 37.6 ms includes engine creation; a long-running application pays it once.
- One-off costs at startup or on the first message of a route; steady state is in scenarios 1–4.

### Scenarios 5b/5c: compiling many scripts and the 1,000-entry script cache (JDK 21, `GroovyScriptCacheTest-jdk21.jmh.json`)

`-prof gc` and `-prof cl` (class loading). 2 forks × 5 × 2 s.

**Compiling N scripts never seen before** (one CamelContext, SingleShotTime):

| scripts | time | per script | allocated | classes loaded per script |
|---:|---:|---:|---:|---:|
| 10 | 8.9 ± 0.3 ms | 0.89 ms | 5.5 MB | 1.00 |
| 100 | 84.6 ± 3.5 ms | 0.85 ms | 49 MB | 1.00 |
| 1,000 | 808 ± 27 ms | 0.81 ms | 484 MB | 1.00 |

~0.8 ms and ~490 KB per script once the Groovy compiler is warm (the 4.3 ms of scenario 5a also creates a new
CamelContext and a new GroovyShell class loader per script).

**Evaluating K distinct scripts round-robin in one context** (the language cache holds 1,000):

| K | per evaluation | per-iteration trend (fork 1 / fork 2, µs) | bytes/op | classes loaded / unloaded per evaluation |
|---:|---:|---|---:|---:|
| 100 | 479 ± 5 ns | flat 0.48 / 0.48 | 1,448 | 0 / 0 |
| 1,000 | **not steady** (mean 7.5 ± 4.9 µs) | **3.0 → 5.2 → 8.0 → 9.9 → 11.4 / 3.0 → 5.0 → 7.9 → 9.9 → 11.4** | 1,697 | 0 / 0 |
| 1,001 | 0.70 ± 0.04 ms | 0.71 / 0.70 | 480,514 | 1.00 / 1.04 |
| 2,000 | 0.70 ± 0.04 ms | 0.71 / 0.70 | 480,777 | 1.00 / 1.08 |

- **Beyond the cache size every evaluation recompiles** (finding 3): 0.70 ms and 480 KB per evaluation, one new class
  per evaluation and the same number unloaded (no Metaspace leak, pure churn), ~1,470× the 100-script cost.
- **With 1,000 cached scripts every evaluation is a cache hit, yet evaluations get slower every iteration.** There is
  no class loading and allocation is constant, but the time goes from 3.0 µs in the first 2 s to 11.4 µs in the fifth
  iteration, identically in both forks: 6–24× the 100-script cost. It is not recompilation. The follow-ups below
  explain it (finding 11). It matters for applications with hundreds of groovy expressions, even below the cache
  size.
- **Follow-up, 20 × 2 s iterations** (`GroovyScriptCacheTest-jdk21-cache-long.jmh.json`, 2 forks). With 1,000
  cached scripts the time per evaluation rises 3.3 → 4.0 → 6.6 → 8.7 → 10.0 → 11.7 → 13.6 µs over the first ~14 s,
  **plateaus at ~14.5–15 µs** around 16–30 s, then eases slightly to ~12.7 µs at 40 s. Both forks are within a few
  percent of each other, still with **0 classes loaded per evaluation**. 100 scripts stay flat at 0.48 µs for all 20
  iterations; 1,001 and 2,000 scripts stay flat at ~0.70 ms (one recompilation per evaluation). The effect is bounded
  (~28× the 100-script cost, and ~50× cheaper than recompiling) and not a leak, but it is a large steady-state cost for
  contexts with hundreds of scripts. A macOS background daemon used ~90% of one core during part of this run.
- **Code cache at the end of each fork** (`-XX:+PrintCodeCache`, `GroovyScriptCacheTest-jdk21-cache-jfr.log`, 1 fork ×
  10 iterations): with 1,000 cached scripts the JIT holds **93.7 MB of C1 profiled (tier 3) code** vs 22.8 MB with 100
  scripts, and only **1.9 MB of C2 code left of a 6.3 MB peak**; 3,390 live nmethods vs 6,739. The code cache never
  filled (`full_count=0`). With 1,001 / 2,000 scripts (recompiling) profiled code is 2.7 / 7.5 MB and C2 code
  9.1 / 10.7 MB.
- **JFR of the same forks rejects a deoptimization storm:** 119 deoptimizations with 100 scripts vs 142 with 1,000
  (same reasons: `unstable_if`, `class_check`, `bimorphic_or_optimized_type_check`, `profile_predicate`). With 1,000
  scripts the JIT compiles more — 10,129 methods in 12.6 s vs 6,425 in 7.3 s — consistent with every script class
  getting its own compiled code, but more compilation does not by itself explain evaluations getting slower over time.
  *Next candidate, not confirmed:* call sites shared by all script classes (binding / property access in the Groovy
  runtime) miss their small invokedynamic call-site caches with 1,000 receiver classes and fall back to metaclass
  method selection. The cpu flamegraph of this benchmark (`followup-cache1000/flame`) should show it.
- **cpu flamegraph of the same benchmark** (`followup-cache1000/flame/…distinctScripts-1000/collapsed-cpu.csv`,
  2,556 samples, vs `…-100`): with 1,000 scripts the top self frames are method handle plumbing executed without
  inlining — `Array.newInstance` 10.4% (varargs argument arrays), `DirectMethodHandle$Holder.invokeVirtual` 5.9%,
  `Class.cast` 5.9%, `LambdaForm$MH…collector` 4.3% + 2.3%, `invokeBasic`, `Invokers.checkCustomized`,
  `checkExactType`, `guard`, `guardWithCatch` (1–3% each) — plus ~3% JIT activity. `GroovyExpression.evaluate` is
  78.1% inclusive, of which `instantiateScript` 16.9% and `createBinding` only 3.3%: **~58% is `script.run()` walking
  invokedynamic call-site chains**. With 100 scripts the profile is the normal one (binding `HashMap`s 47%,
  instantiation 21%, property access 7.5%). The metaclass-cache candidate above is not what the profile shows.
- **Explanation consistent with all the data (profile, code cache, JFR):** every script class has its own
  invokedynamic call sites (`body`, `header`, `foo`, `+`). Round-robin over 1,000 scripts gives each script's `run()`
  1/1,000 of the calls, so it stays in C1 tier-3 profiled code (the 93.7 MB of profiled code) and rarely reaches C2,
  the tier that inlines the call-site method handle chains; each property access then walks the method handle chain.
  With 100 scripts each `run()` gets 10× more calls and reaches C2. This explains the plateau; the exact mechanism of
  the gradual rise over the first ~15 s is plausible (scripts moving from interpreter to profiled code) but not proven.
- **Implication for camel-groovy:** contexts with many distinct, rarely executed groovy expressions pay invokedynamic
  dispatch in code the JIT never fully optimizes. This is the case where an opt-in static compilation mode could pay
  off (static compilation replaces invokedynamic with ordinary calls that C1 handles well) — unlike scenario 3, where
  closures dominated. *Not measured yet:* the same benchmark with a `@CompileStatic` shell factory, and with
  `-XX:-TieredCompilation`.

### Scenario 5d: script cache churn harness (JDK 21, `GroovyScriptCacheChurnTest-jdk21.txt` and `-softref0.txt`)

Deterministic harness (not JMH): each script returns its own class, so a new class identity means a recompilation;
only weak references to the classes are kept. Run with the default soft reference policy and with
`-XX:SoftRefLRUPolicyMSPerMB=0` (soft references are cleared at a GC if not used since the previous one — an option
some teams set when tuning GC).

| check | default policy | `SoftRefLRUPolicyMSPerMB=0` |
|---|---|---|
| 1,000 distinct scripts, 3 rounds (3,000 evaluations) | **0 recompilations**, 3.8 µs / evaluation | **1,083 recompilations (36%)**, 449 µs / evaluation |
| 1,001 distinct scripts, 3 rounds | 3,003 recompilations (every evaluation), 754 µs | 3,003, 744 µs |
| 2,000 distinct scripts, 3 rounds | 6,000 recompilations, 490 µs | 6,000, 489 µs |
| classes loaded / unloaded (1,001 scripts) | +3,006 / +3,003 | +3,026 / +3,025 |
| Metaspace before / peak / after GC (1,001 scripts) | 27.7 / 36.7 / 27.8 MB | 24.7 / 33.8 / 24.8 MB |
| hot script used after every one of 1,500 new cold scripts | recompiled once, right after cold script #1,000 | same |
| 8 threads evaluate a new script at the same time (50 trials) | 8.00 compilations per script (max 8) | same |
| 50 scripts, two `System.gc()` between rounds | 0 recompiled | **50 of 50 recompiled every round** (36–53 ms per round) |

- **FIFO eviction confirmed** (finding 3): a script used right after every insertion is still evicted by the 1,000th
  newer script; an LRU cache would never evict it.
- **Duplicate compilation confirmed** (finding 4): 8 concurrent first uses compile 8 classes.
- **No Metaspace leak:** evicted classes are unloaded and Metaspace returns to its baseline after GC; the cost is CPU,
  allocation and GC work (scenario 5c, load test).
- **Soft references:** with the default policy nothing is cleared on this mostly empty heap. With
  `SoftRefLRUPolicyMSPerMB=0` every script not used between two GCs is recompiled even though the cache is not full:
  36% of the round-robin evaluations over 1,000 scripts recompiled. Applications with rarely used groovy expressions
  (error handlers, admin routes) and aggressive soft reference tuning recompile them on almost every use.
- The default-policy 1,000-script round robin averages 3.8 µs per evaluation (no recompilation) — far above the 479 ns
  measured with 100 scripts, consistent with the unexplained slowdown of scenario 5c (follow-up running).

### Scenario 6: where a groovy evaluation spends its time (JDK 21, `GroovyOverheadTest-jdk21.jmh.json`)

Script `body + '-' + header.foo`, one reused exchange. ns/op = 1e9 / throughput.

**Whole evaluation** — camel-groovy on main vs the benchmark-local prototypes (`OptimizedGroovyExpression`; the
camel-groovy branch prototype is measured separately in the prototype phase):

| registry | evaluate (main) | bytes | prototype: lookups once + cached class + MethodHandle | bytes | prototype + lazy binding | bytes |
|---|---:|---:|---:|---:|---:|---:|
| 0 extra beans, no `GroovyShellFactory` | 297 ns (3,362,248 ± 19,360 ops/s) | 1,400 | 175 ns | 1,160 | **55 ns** | 248 |
| 0 extra beans, factory with file name | 392 ns (2,552,970 ± 20,817) | 2,000 | 175 ns | 1,160 | 55 ns | 248 |
| 500 extra beans, no factory | **3,522 ns** (283,929 ± 982) | 1,480 | 175 ns | 1,160 | 55 ns | 248 |
| 500 extra beans, factory with file name | **5,624 ns** (177,819 ± 3,344) | 2,000 | 175 ns | 1,160 | 55 ns | 248 |

**Steps of one evaluation on main** (0 extra beans, no factory):

| step | ns/op | bytes/op |
|---|---:|---:|
| `resolveLanguage("groovy")` | 7.0 | 24 |
| `registry.findByType(GroovyShellFactory.class)` | 20.8 | 80 |
| `fileName + text` key + cache lookup (with a factory) | 19.0 (±11%) | 88 |
| `instantiateScript` (the three above + reflective `newInstance`) | 70.3 | 240 |
| reflective `Script` instance | 26.1 | 160 |
| `MethodHandle` `Script` instance (alternative) | 13.6 | 48 |
| `createBinding` (includes the 48 B map argument) | 154 | 1,152 |
| `script.run()` with a prebuilt binding | 48.2 | 104 |
| result conversion | 1.7 | 0 |

Reading the tables:

- **The script itself is ~48 ns of the ~297 ns.** Binding creation (154 ns, 1.15 KB) and instance/lookup work (70 ns)
  are the rest; the steps add up to ~274 ns.
- **Registry size multiplies the cost:** with 500 unrelated beans every evaluation is 11.8× slower (3.5 µs), because
  `findByType` scans every bean on every evaluation; a `GroovyShellFactory` with a file name adds ~95 ns and 600 bytes
  (key concatenation, globals map).
- **Resolving once removes the dependency on the registry** (175 ns flat), and **the lazy binding brings an
  evaluation to 55 ns / 248 bytes: 5.4× faster than main with no extra beans, 64× with 500 beans, 102× with 500 beans
  and a factory.** A `MethodHandle` saves ~12 ns per evaluation over reflection — small next to the binding.

### Scenario 7a: groovyJson vs Jackson (JDK 21, `GroovyJsonDataFormatTest-jdk21.jmh.json`)

AverageTime (µs per operation ± 99.9% error) and bytes allocated per operation, through the Camel `DataFormat`
(`marshal(exchange, graph, ByteArrayOutputStream)` / `unmarshal(exchange, InputStream)`). Payload: a list of orders with
nested items, ~1 KB and ~1 MB. The setup checks that every variant produces the same JSON document; this build
includes CAMEL-24669, so groovyJson `prettyPrint=false` is equal work (no `NOT equal work` warning in the log).

| operation | 1 KB | bytes | vs Jackson | 1 MB | bytes | vs Jackson |
|---|---:|---:|---:|---:|---:|---:|
| unmarshal Jackson (to `Map`) | 2.9 µs | 7,956 | 1.00× | 2,655 ± 24 µs | 7.2 MB | 1.00× |
| unmarshal groovyJson (`JsonSlurper`) | 3.2 µs | 26,544 | 1.10× | 2,946 ± 39 µs | 10.9 MB | 1.11× |
| unmarshal + read every value, Jackson | 4.2 µs | 10,476 | 1.00× | 3,894 ± 37 µs | 10.0 MB | 1.00× |
| unmarshal + read every value, groovyJson | 5.6 µs | 42,240 | 1.33× | 5,468 ± 253 µs | 27.6 MB | 1.40× |
| unmarshal + read every value, `JsonSlurper` `INDEX_OVERLAY` | 5.5 µs | 36,120 | 1.31× | 4,554 ± 355 µs | 21.2 MB | 1.17× |
| marshal Jackson compact | 1.9 µs | 2,936 | 1.00× | 1,848 ± 152 µs | 3.8 MB | 1.00× |
| marshal Jackson pretty | 2.7 µs | 3,856 | 1.42× | 3,150 ± 251 µs | 6.3 MB | 1.70× |
| **marshal groovyJson pretty (default `prettyPrint=true`)** | **60.8 µs** | **352,482** | **32.0×** | **55,613 ± 182 µs** | **242.9 MB** | **30.1×** |
| marshal groovyJson compact (`prettyPrint=false`) | 13.5 µs | 117,508 | 7.1× | 5,981 ± 48 µs | 17.9 MB | 3.2× |
| `JsonOutput.toJson(map)` (what compact does) | 13.4 µs | 116,152 | 7.1× | 5,909 ± 18 µs | 16.6 MB | 3.2× |
| `StreamingJsonBuilder` (candidate, no intermediate String) | 13.8 µs | 120,928 | 7.3× | 5,935 ± 47 µs | 20.0 MB | 3.2× |

Reading the table:

- **Unmarshal is close to Jackson** (1.1×; 1.3–1.4× when every value is read) but allocates 1.5–3.3× more. The
  `INDEX_OVERLAY` parser is 17% faster than the default `CHAR_BUFFER` at 1 MB when every value is read (and the same at
  1 KB) — a small, safe candidate for large documents.
- **Marshal is where groovyJson loses:** the default pretty print re-parses and re-serializes the compact text
  (finding 5), costing **4.5× (1 KB) to 9.3× (1 MB) over groovyJson's own compact output** and ~30× Jackson, with
  243 MB allocated per 1 MB document. Compact output is still 3–7× Jackson and allocates ~5–40× more.
- **`StreamingJsonBuilder` is not a fix:** removing the intermediate `String` saves nothing measurable; the cost is in
  Groovy's JSON generator itself.

### Scenario 7b: groovyXml vs JAXP / StAX / jacksonXml (JDK 21, `GroovyXmlDataFormatTest-jdk21.jmh.json`)

AverageTime (µs per operation) and bytes allocated per operation. Unmarshal parses the same document in every variant
(element counts checked: groovy `Node`, DOM and StAX agree; jacksonXml is only checked to return a `Map`). Marshal
writes the same `Map`, but **the documents differ**: groovyXml maps `_id` / `_sku` to attributes (41 elements for
1 KB), jacksonXml to elements (54), so the marshal comparison is close but not equal work.

| operation | 1 KB | bytes | 1 MB | bytes |
|---|---:|---:|---:|---:|
| unmarshal StAX scan (reads every event, builds no tree) | 3.4 µs | 4,480 | 3,306 ± 74 µs | 2.5 MB |
| unmarshal jacksonXml (to `Map`) | 6.1 µs | 9,736 | 6,087 ± 46 µs | 7.1 MB |
| unmarshal DOM (`DocumentBuilder`, cached factory) | 16.4 µs | 39,416 | 6,613 ± 21 µs | 4.9 MB |
| **unmarshal groovyXml (`new XmlParser()` per call)** | **33.2 µs** | **66,481** | **9,274 ± 99 µs** | **17.6 MB** |
| unmarshal groovy `XmlParser` with a cached `SAXParserFactory` (candidate) | 18.3 µs | 43,633 | 9,304 ± 72 µs | 17.6 MB |
| marshal `Map` jacksonXml | 3.0 µs | 4,856 | 3,087 ± 12 µs | 6.4 MB |
| **marshal `Map` groovyXml** | **7.4 µs** | **25,576** | **9,406 ± 537 µs** | **27.4 MB** |
| marshal `Map` jacksonXml to an unbuffered `FileOutputStream` | 3.7 µs | 2,872 | 3,700 ± 22 µs | 1.5 MB |
| marshal `Map` groovyXml to an unbuffered `FileOutputStream` | 252.4 µs | 21,928 | 261,428 ± 2,078 µs | 22.5 MB |
| marshal `Map` groovyXml to a `BufferedOutputStream` | 9.6 µs | 20,848 | 9,891 ± 847 µs | 22.0 MB |

Reading the table:

- **groovyXml unmarshal builds a Groovy `Node` tree** at ~2× DOM and 5× jacksonXml for 1 KB, and 1.4–1.5× for 1 MB,
  allocating 2–3.5× more.
- **`new XmlParser()` per call costs ~15 µs** (a `SAXParserFactory` lookup and configuration each time): caching the
  factory makes 1 KB unmarshal 1.8× faster; at 1 MB the parse dominates and it makes no difference. A small-document
  optimization (the parser itself is not thread safe, the factory can be shared or kept per thread).
- **Map → XML marshal is 2.5–3× jacksonXml** and allocates 4–5× more (per-value `TypeConverter` calls and one
  `String.getBytes()` per fragment).
- **The many tiny `os.write()` calls cost 34× (1 KB) / 28× (1 MB) on an unbuffered stream** (one system call each).
  This only affects code calling `DataFormat.marshal` with a raw stream: the Marshal EIP writes into
  `OutputStreamBuilder` (`CachedOutputStream` / `ByteArrayOutputStream`), where groovyXml is at its 7.4 µs / 9.4 ms.

## 5. Long running high load: heap behaviour

All variants over the **same window, 60–300 s** (8 producer threads, 1 GB heap, G1, unbounded rate unless noted;
10 minute runs cut to 60–300 s with `load_tables.py --until 300`, whose averages match their full 60–600 s window
within 1%). Route: filter(amount > 100) → setHeader(vip = any of 20 line items > 90) → setBody(concat) → counter;
bytes/msg per sent message.

**Harness and classpath versions:** all rows except the 900-script row ran at 13:36–15:41. That was before the harness
fix `a515a5f` (16:00: per-thread latency histograms, all G1 pause beans, old gen from GC notifications), and the
java, groovy, groovyPrototype, 1,500-script and 100,000 msg/s rows also ran before the benchmark classpath gained the
other languages (`d89d866`, 14:49). The 900-script row (18:25) uses the current harness and classpath. Java and groovy
were re-run on the current harness and classpath (section 9): java measures 4,109,230 msg/s (+3.8%), groovy
1,082,957 (+2.8%, 26% of java). Bytes per message were unchanged. Heap after young GC rose from 10 / 18 MB to 17 /
26 MB, because of 5 MB of humongous regions that come with the larger classpath. jactl, mvel, java (jOOR), js and
python3 were not re-run. Differences of a few percent between the Java-like variants below are therefore not
significant, and memory figures are only comparable between runs with the same classpath.

| variant | msg/s | vs java | p99 µs (median / max) | bytes/msg | GC pauses/s | pause % | old gen after GC | Metaspace | CPU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| java | 3,958,295 | 100% | 2 / 4 | 1,538 | 9.5 | 0.90 | 0.0 MB | 17.1 → 17.2 MB | 80% |
| jactl | 3,731,657 | 94% | 3 / 5 | 1,626 | 9.5 | 0.94 | 14.8 MB flat | 21.2 → 21.4 MB | 78% |
| groovyPrototype (benchmark-local) | 3,722,592 | 94% | 3 / 5 | 2,779 | 16.2 | 1.55 | 8.5 MB flat | 28.3 → 28.4 MB | 79% |
| mvel | 3,676,944 | 93% | 3 / 6 | 1,835 | 10.6 | 1.00 | 0.0 MB | 18.4 → 18.5 MB | 78% |
| java (jOOR) | 3,532,546 | 89% | 4 / 6 | 1,570 | 8.7 | 0.85 | 44.6 MB flat | 26.9 → 27.1 MB | 78% |
| groovy | 1,053,471 | 27% | 105 / 109 | 5,566 | 9.2 | 0.88 | 8.4 MB flat | 28.4 → 28.6 MB | 47% |
| groovyManyScripts, 900 cached scripts (5 min, `e1d8cc6fee92`) | 933,913 | 24% | 98 / 99 | 5,542 | 8.1 | 0.95 | 76 MB flat (GC log) | 65.4 → 65.5 MB | 51% |
| groovyManyScripts (1,500 scripts) | 5,019 | 0.13% | 5,550 / 8,500 | 233,579 | 3.0 | 5.22 | 373 → 657 max → 592 MB | 62.8 → 77.6 MB | 47% |
| js (GraalJS) | 4,697 | 0.12% | 4,300 / 5,600 | 1,767,305 | 13.0 | 2.12 | 22.4 MB flat | 40.7 → 40.8 MB | 68% |
| python3 (GraalPy) | 277 | 0.007% | 53,050 / 144,300 | 12,839,279 | 6.9 | 1.45 | 46.5 MB flat | 90.5 → 90.8 MB | 72% |
| java at 100,000 msg/s | 100,000 | | 5 / 6 | 1,538 | 0.24 | 0.03 | 0.0 MB | 17.0 → 17.2 MB | 4% |
| groovy at 100,000 msg/s | 100,000 | | 10 / 21 | 5,550 | 0.87 | 0.08 | 8.8 MB flat | 28.4 → 28.5 MB | 7% |

Reading the table:

- **Java-like tier:** jactl, mvel and java (jOOR) reach 89–94% of the Java route with 1.6–1.8 KB per message and the
  same CPU saturation (78%). The benchmark-local groovy prototype reaches the same tier (94%) but still allocates
  1.8× Java per message.
- **groovy (main):** 27% of Java, 3.6× the allocation per message, and only 47% CPU: the 8 threads wait on the
  `DefaultRegistry` `Stack` monitor (finding 1), which is also why p99 is 105 µs.
- **900 distinct scripts that fit in the cache:** once warm, the route runs at 934k msg/s. That is 86% of the same
  route with 3 scripts on the same harness and classpath (the section 9 re-run, 1,083k msg/s), with about the same p99
  (98 vs 102 µs), the same bytes per message, no class loading and a flat heap. The costs are memory: heap after young
  GC 76 MB instead of 26 MB, and Metaspace 65.5 MB instead of 28.6 MB, again against the same-classpath re-run. That
  is ~87 MB for 900 compiled script classes and their runtime state. There is also a JIT warm-up: throughput halves to
  430–480k msg/s between 15 and 25 s
  while CPU peaks at 84–93%, and recovers by ~50 s. Crossing the 1,000 entry cache (1,500 scripts) is what collapses
  the route (186× slower). The scenario 5c slowdown does not show here because each script runs ~260 times per second,
  enough for the JIT to reach C2; it applies to scripts that run rarely.
- **Heap under sustained load:** no variant grows its heap during the window except `groovyManyScripts` (script
  cache churn, see below). The "old gen after GC" column in this table is a stale harness value; the heap after young
  GC from the GC logs is flat for every other variant (java 10 MB, mvel 17, groovy 18, jactl and prototype 19, js 24,
  python3 52, jOOR 61 — *suspected* compiler state).
- **js / python3:** 840× and 14,000× below Java. Every evaluation creates a new polyglot `Context` and the Graal
  engine runs `Interpreted` on this JDK, so each message allocates 1.8 MB / 12.8 MB. Python3 also has the largest
  Metaspace (90.8 MB). The js run overlapped Spotlight indexing (about 1 core).
- **Equal traffic (100,000 msg/s):** groovy allocates 3.6× Java (529 vs 147 MB/s), which gives 3.6× the young GC
  pauses (0.87 vs 0.24 per second); the pause share stays small (0.08% vs 0.03%) and p99 doubles (10 vs 5 µs).
- **Caveats:** java/groovy/groovyPrototype/groovyManyScripts/fixed-rate ran on `364a17a0f752`, the languages on
  `e1d8cc6fee92` (identical code in the tested paths); one laptop, one run per variant; max values depend on the window
  (see the 10 minute figures below).

**GC figures from the GC logs** (the source of truth; `gc_log_tables.py`, window 60–300 s). The harness columns
"GC pauses/s", "pause %" and "old gen after GC" in the tables above and below are superseded: the harness ignored the
JDK 20+ "G1 Concurrent GC" bean that reports the Remark and Cleanup pauses, rounded every pause down to whole
milliseconds (~7% low), and read the old generation's collection usage, which G1 only refreshes on mixed/full
collections (a startup value for every run except groovyManyScripts). The harness is fixed for later runs.

| run | STW pauses/s | pause % | max pause ms | young | mixed | remark | cleanup | full | heap after young GC, MB (first ⅓ / last ⅓ of the window) |
|---|---:|---:|---:|---|---|---|---|---|---:|
| java | 9.52 | 0.97 | 5.0 | 2,284 / 2,322 ms | 0 | 0 | 0 | 0 | 10.0 / 10.0 |
| jactl | 9.49 | 1.01 | 1.9 | 2,277 / 2,418 ms | 0 | 0 | 0 | 0 | 19.0 / 19.0 |
| mvel | 10.56 | 1.08 | 4.0 | 2,534 / 2,581 ms | 0 | 0 | 0 | 0 | 17.0 / 17.0 |
| java (jOOR) | 8.68 | 0.93 | 12.1 | 2,083 / 2,225 ms | 0 | 0 | 0 | 0 | 61.0 / 61.0 |
| groovyPrototype | 16.16 | 1.66 | 3.0 | 3,879 / 3,985 ms | 0 | 0 | 0 | 0 | 19.0 / 19.0 |
| groovy | 9.16 | 0.94 | 1.8 | 2,199 / 2,253 ms | 0 | 0 | 0 | 0 | 18.0 / 18.2 |
| groovyManyScripts, 900 cached scripts | 8.11 | 1.00 | 1.5 | 1,947 / 2,411 ms | 0 | 0 | 0 | 0 | 76.0 / 76.0 |
| groovyManyScripts | 4.53 | **7.63** | 69.9 | 438 / 7,383 ms | 273 / 5,105 ms | **187 / 5,704 ms** | 187 / 50 ms | 1 / 70 ms | 568.7 / 570.0 |
| js | 13.03 | 2.20 | 3.4 | 3,127 / 5,272 ms | 0 | 0 | 0 | 0 | 24.4 / 24.4 |
| python3 | 6.92 | 1.53 | 17.9 | 1,660 / 3,660 ms | 0 | 0 | 0 | 0 | 52.8 / 51.8 |
| java at 100,000 msg/s | 0.24 | 0.03 | 2.4 | 57 / 71 ms | 0 | 0 | 0 | 0 | 9.0 / 9.0 |
| groovy at 100,000 msg/s | 0.87 | 0.09 | 2.3 | 208 / 222 ms | 0 | 0 | 0 | 0 | 18.0 / 18.0 |

Over the full 60–600 s of the 10 minute runs: groovyManyScripts 41,008 ms of pauses = **7.58%** (young 16.8 s, mixed
11.2 s, Remark 12.8 s in 424 pauses averaging 30 ms, 3 full GCs 211 ms); java 0.99% (one 134 ms pause, the macOS
scheduling stall described below), groovy 0.94%, groovyPrototype 1.65%.

What the GC logs change in the reading of this section:

- **No heap growth in any normal variant**: the heap right after young collections is the same at the start and at
  the end of the window (java 10 MB, mvel 17, groovy 18, jactl and the prototype 19, js 24, python3 52, jOOR 61), and
  none of them needed a mixed, remark or full collection after warmup. The different baselines are live data kept by
  each runtime (the jOOR 61 MB is *suspected* javac/jOOR compiler state, not confirmed).
- **groovyManyScripts**: the 187 Remark pauses (30 ms each, class unloading of the recompiled scripts) are a third
  of the pause time and the likely driver of the multi-ms p99.9, more than the single ~70 ms full GC in the window.
- **Allocation is not what limits the unbounded runs**: groovyPrototype allocates ~9.9 GB/s, more than java
  (~5.8 GB/s). Java and the Java-like languages are CPU-bound (≈8 of the 10 logical CPUs busy); groovy on main is
  held back by monitor contention (47% CPU), not by GC (0.94% pause time). Groovy's 3.6× allocation per message costs
  3.6× the young collections at equal traffic (100,000 msg/s: 0.87 vs 0.24 pauses/s), with a small pause share.

Per-run details (full windows):

Full runs so far (600 s, 8 threads, 1 GB heap, unbounded rate, first 60 s excluded):

| variant | msg/s sent | p99 | bytes/msg | GC pauses/s | pause time | old gen after GC | Metaspace | CPU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| java | 3,933,611 | 2 µs | 1,537 | 9.5 | 0.92% | 0.0 MB | 17.1 → 17.3 MB | 79% |
| groovy | 1,050,322 | 105 µs | 5,566 | 9.1 | 0.87% | 8.4 MB (flat) | 28.4 → 28.6 MB | 46% |
| groovyPrototype (benchmark-local `OptimizedGroovyExpression`, lazy binding) | 3,715,957 | 3 µs | 2,779 | 16.1 | 1.54% | 8.5 MB (flat) | 28.3 → 28.5 MB | 79% |
| jactl (5 min run, `e1d8cc6fee92`) | 3,731,651 | 4 µs (p99.9 9 µs) | 1,625 | 9.5 | 0.93% (max 2 ms) | 14.8 MB (flat) | 21.2 → 21.4 MB | 78% |
| mvel (5 min run, `e1d8cc6fee92`) | 3,676,944 | 3 µs (p99.9 8 µs) | 1,835 | 10.5 | 1.00% (max 2 ms) | 0.0 MB | 18.4 → 18.5 MB | 78% |
| js / GraalJS (5 min run, `e1d8cc6fee92`; new `Context` per evaluation, engine `Interpreted`; Spotlight indexing during the run) | 4,697 | 4.5 ms (p99.9 5.9 ms) | 1,767,310 | 13.0 | 2.12% (max 3 ms) | 22.4 MB (flat) | 40.7 → 40.8 MB | 68% |
| java / jOOR (5 min run, `e1d8cc6fee92`) | 3,532,542 | 4 µs (p99.9 12 µs) | 1,569 | 8.7 | 0.85% (max 9 ms) | 44.6 MB (flat; *suspected* javac/jOOR compiler state kept after compiling, to confirm with JFR) | 26.9 → 27.1 MB | 78% |
| groovyManyScripts (1,500 distinct scripts, round robin) | 5,010 | 5.6 ms (p99.9 36.6 ms) | 233,727 | 2.9 | 5.17% (3 full GCs, max 70 ms) | 199–739 MB (first 373, last 426) | 62.8 → 68.9 MB | 46% |

What the unbounded runs show so far:

- Groovy allocates **3.6× more per message** (5,566 vs 1,537 bytes). ~~Both routes allocate ~5.6–5.8 GB/s, so the
  allocation rate is limited by the machine~~ — corrected: the prototype allocates ~9.9 GB/s, so allocation is not
  the limit; see the GC-log table above.
- No heap growth in 10 minutes (heap after young GC 10 MB java / 18 → 19 MB groovy, from the GC log; the harness
  "old gen after GC" value was stale), Metaspace is +11 MB versus Java and flat, no classes loaded after warmup.
- Groovy runs at 46% CPU with 8 producer threads (Java 79%): the threads wait on the `DefaultRegistry` `Stack`
  monitor (finding 1), which also explains p99 = 105 µs versus 2 µs.
- The benchmark-local prototype (shell factory looked up once, compiled class kept on the expression, lazy binding)
  gets the same Groovy scripts to 3.7 M msg/s (94% of Java), p99 3 µs and 79% CPU, and halves the allocation per
  message (2,779 bytes). Its GC pauses/s are higher only because it moves 3.5× more messages. This prototype has no
  dev-reload handling; the camel-groovy branch prototype is measured in the `prototype` phase.
- **More than 1,000 distinct scripts is where the heap suffers.** With 1,500 scripts in rotation every evaluation of
  the `setBody` script recompiles (finding 3): throughput drops ~200× to 5,010 msg/s, each message allocates ~234 KB,
  1,365,869 script classes are loaded and 1,364,381 unloaded in 10 minutes (~2,300 per second), the old generation
  after GC swings between 199 and 739 MB of the 1 GB heap, GC takes **7.6%** of the wall time according to the GC log
  (the harness reported 5.2% because it missed the Remark pauses: 424 × ~30 ms of class unloading) with 3 full GCs, and
  p99.9 latency reaches 36.6 ms. This is churn, not a leak: Metaspace stays at 63 → 69 MB, and the three full GCs
  (`Pause Full (G1 Compaction Pause) 1023M->36M`, ~70 ms, roughly every 170 s) find only 36 MB live. Between them G1
  runs back-to-back `Pause Young (Concurrent Start)` collections (~17 ms, 900 MB → 510–600 MB), i.e. the old
  generation keeps filling with dead compiler output. The first full GC (at 157 s) shows the mechanism in the GC log:
  a concurrent mark cycle ends with `Pause Remark 956M->911M` (little found reclaimable), the following mixed
  collection fails (`GC(585) Pause Young (Mixed) (Evacuation Failure) 952M->965M`), the next young collection fails
  too (`GC(586) ... (Evacuation Failure) 1010M->1023M`), and G1 falls back to `GC(588) Pause Full 1023M->36M`.
  *Inference, not measured:* the compiler output stays reachable through the script classes and their class loaders
  until G1 unloads those classes at Remark, so concurrent marking cannot reclaim it in time; either way, only 36 MB is
  live.
- The fixed-rate runs (100k msg/s) compare GC load at equal traffic.

Fixed rate, 100,000 msg/s sent (600 s, 8 threads, 1 GB heap, first 60 s excluded):

| variant | msg/s sent | p99 (p99.9) | bytes/msg | alloc MB/s | GC pauses | pause time | old gen after GC | Metaspace | CPU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| java | 99,931 | 5 µs (17 µs) | 1,538 | 147 | 129 (0.2/s), max 2 ms | 133 ms (0.02%) | 0.0 MB | 17.0 → 17.2 MB | 4% |
| groovy | 99,947 | 10 µs (max 21 µs) | 5,550 | 529 | 0.87/s, max 2 ms | 0.08% | 8.8 MB | 28.4 → 28.6 MB | 7% |

Noise note: the Java run has one 134 ms young pause (GC(3000), 623M→10M like its neighbours at ~1 ms) with
`User=0.00s Sys=0.00s Real=0.14s` in the GC log: the GC threads were not scheduled by macOS, the collector did no
extra work. Max-pause values from this laptop must be read with that in mind.

## 6. Profiles

### Full-run profiles (JDK 21, async-profiler 4.5)

HTML flamegraphs: `raw/flamegraphs/<event>/…`; collapsed stacks used for the percentages below:
`raw/flamegraphs-collapsed/<event>/…` (1 fork, 2 × 5 s, cpu sampling at the default interval; percentages are shares of
all samples of that benchmark, "inclusive" = frame anywhere on the stack).

**groovy vs Java concat expression (scenario 1, cpu):**

| | groovy `body + '-' + header.foo` (1,032 samples) | Java `Expression` (1,035 samples) |
|---|---|---|
| inclusive | `GroovyExpression.evaluate` 94.6% → **`createBinding` 64.5%**, **`instantiateScript` 23.0%**, script body (`dgm…doMethodInvoke` / `StringGroovyMethods.plus`) ~3%, metaclass lookup (`GroovyObjectSupport.<init>` → `MetaClassRegistryImpl.getMetaClass`) 2.7% | the expression 64.0%, the rest is the benchmark's property set |
| top self frames | `HashMap.resize` 10.4%, `HashMap.putVal` 8.6%, `AbstractExchange.getInternalProperties` 5.9%, `EnumMap.get` 4.8%, `HashSet.<init>` 4.8%, `HashMap.newNode` 3.9%, `EnumMap.unmaskNull` 3.7%, `String.hashCode` 3.1%, `HashMap.putMapEntries` 2.9%, `Constructor.newInstanceWithCaller` 1.9% | `GroovyExpressionTest.concat` 10.4%, `jbyte_disjoint_arraycopy` 10.2%, `CaseInsensitiveMap.caseInsensitiveHash` 9.3%, `ExchangePropertyKey.asExchangePropertyKey` 7.5%, `String.getBytes` 6.1%, `CaseInsensitiveMap.findIndex` 5.4% |

The profile matches the step benchmark (scenario 6): nearly two thirds of a groovy evaluation is building the binding
maps (including the `getAllProperties()` copy of the internal exchange properties), a quarter is getting a `Script`
instance, and the script itself is a few percent.

**groovy vs Java route, 1 thread (scenario 4, cpu):**

| | groovy route (1,015 samples) | Java route (1,005 samples) |
|---|---|---|
| route logic (filter + setBody) | **`GroovyExpression.evaluate` 49.9%** (two evaluations per message): `createBinding` 37.0%, `instantiateScript` 8.7%, metaclass lookup 1.7% | **Java lambdas ~2.4%** (`evaluate` 1.7%, `matches` 0.3%, counter 0.4%) |
| top self frames | `HashMap.putVal` 13.6%, `itable stub` 5.7%, `HashMap.resize` 4.9%, `AbstractQueuedSynchronizer.getState` 3.4%, `CamelInternalProcessor.process` 2.4%, `Pipeline.process` 2.3%, `AdviceIterator.runAfterTasks` 2.2%, `ConcurrentHashMap.get` 2.1% | `itable stub` 10.9%, `Pipeline.process` 7.1%, `CamelInternalProcessor.process` 5.5%, `mach_absolute_time` 4.1%, `AdviceIterator.runAfterTasks` 3.8%, `ExchangeHelper.isErrorHandlerBridge` 3.4%, `ConcurrentHashMap.get` 2.9% |

In the Java route the route logic is noise and the CPU is Camel's routing engine (exchange creation, pipeline,
internal processors). In the groovy route **half of all CPU is the two groovy evaluations, three quarters of that the
binding maps** — the 2.1× single-thread gap of scenario 4. `AbstractQueuedSynchronizer.getState` (3.4%) appears in the
groovy profile only, on a single thread; its caller is not broken down here (observed, not explained).

**groovyJson `marshal` with the default `prettyPrint=true` (scenario 7a, cpu):**

| | 1 KB (1,025 samples) | 1 MB (1,048 samples) |
|---|---|---|
| inclusive | `GroovyJSonlDataFormat.serialize` 96.7% → **`JsonOutput.prettyPrint` 74.9%** (`JsonLexer.nextToken` 60.9%), `DefaultJsonGenerator.writeObject` 21.2% | `serialize` 95.0% → **`JsonOutput.prettyPrint` 83.7%** (`JsonLexer.nextToken` 69.5%, `JsonTokenType.matching` 26.4%) |
| top self frames | **`ConcurrentLinkedHashMap.<init>` 12.2%**, `BufferedReader.read` 7.9%, `JsonOutput.getIndent` 6.4%, `JsonLexer.skipWhitespace` 3.8%, `BufferedReader.reset` 3.6%, `String.charAt` 3.1%, `CharBuf.<init>` 2.8% | `BufferedReader.read` 8.2%, `JsonOutput.getIndent` 5.7%, `CharBuf.<init>` 4.4%, `Writer.write` 3.9%, `JsonLexer.skipWhitespace` 3.9%, `StringEscapeUtils.unescapeJava` 3.2%, `Pattern$Branch.match` 3.1%, `Pattern$GroupHead.match` 2.6% |

Serializing the map is ~21% at 1 KB; **75–84% of the CPU is `JsonOutput.prettyPrint` lexing the text that was just
produced**, with Groovy's lexer reading through a `BufferedReader` and matching tokens with regular expressions
(`JsonTokenType.matching`, `java.util.regex`), plus a new `ConcurrentLinkedHashMap` per call (12% at 1 KB). All of
it is inside Groovy's `JsonOutput`, so the fix belongs in camel-groovy's use of it (finding 5: indent while
generating instead of calling `prettyPrint`), not in patching Groovy.

**groovyXml `unmarshal` and `Map` `marshal` (scenario 7b, cpu):**

| | 1 KB | 1 MB |
|---|---|---|
| unmarshal, inclusive | **`XmlParser.<init>` 61.4%** (`FactorySupport.createFactory` 29.3%), `XmlParser.parse` 37.6% (1,010 samples) | `XmlParser.parse` 92.0% (`startElement` 12.2%, `addTextToNode` 9.0%, `endElement` 5.9%) (1,071 samples) |
| unmarshal, top self | `stat64` 8.5%, `String.equals` 8.1%, `pthread_jit_write_protect_np` 4.7%, `ParserConfigurationSettings.setFeature` 2.6%, `HashMap.resize` 2.5%, `URLClassPath$1.next` 1.8% | `XMLEntityScanner.scanQName` 11.0%, `XMLNSDocumentScannerImpl.scanStartElement` 9.1%, `FragmentContentDriver.next` 8.4%, `skipString` 4.9%, `String.<init>` 4.3% |
| marshal `Map`, inclusive | `printLines` 67.4%, `doSerialize` 28.0%, `Line.<init>` 3.6% (1,034 samples) | `printLines` 70.7%, `doSerialize` 27.7%, `Line.<init>` 3.5% (1,013 samples) |
| marshal `Map`, top self | `ByteArrayOutputStream.write` 11.5%, `String.encodeUTF8` 7.0%, `OutputStream.write` 6.1%, `printLines` 5.8%, `doSerialize` 5.4%, `String.getBytes` 5.3% | `ByteArrayOutputStream.write` 12.0%, `arrayof_jlong_disjoint_arraycopy` 11.2%, `String.getBytes` 7.9%, `String.encodeUTF8` 6.2%, `OutputStream.write` 6.1% |

- **For small documents most of the unmarshal is creating the parser:** `new XmlParser()` → `SAXParserFactory` lookup
  (`FactorySupport.createFactory`), which searches the class path for a factory implementation — the `stat64` and
  `URLClassPath` frames — and configures features, 61% of the 1 KB unmarshal before a byte is parsed. That part scales
  with the class path, so it can be larger in big applications. At 1 MB it disappears into the parse.
- **Marshal is mostly writing:** ~70% in `printLines`, one `String.getBytes()` (UTF-8 encoding) and one
  `OutputStream.write` per fragment; building the `Line` records with a type conversion per value is ~28%.

**groovy vs Java route, 8 threads (scenario 4, cpu and lock):**

| | groovy route (5,386 cpu samples) | Java route (8,009 cpu samples) |
|---|---|---|
| cpu, inclusive | `GroovyExpression.evaluate` 72.2% → **`instantiateScript` 53.0%**, `createBinding` 16.4% | route logic < 1%; the rest is the routing engine |
| cpu, top self | **`__psynch_cvwait` 17.9%, `ObjectMonitor::TrySpin` 7.9%, `__psynch_cvsignal` 3.5%**, `SimpleRegistry.findByType` 6.3%, `HashMap.putVal` 6.0% | `itable stub` 9.2%, `os::javaTimeNanos` 8.9%, `Pipeline.process` 6.4%, `CaseInsensitiveMap.init` 6.1% |
| lock | 241,738 samples, **100% `java.util.Stack`** via `instantiateScript` → `DefaultRegistry.findByType` → `getLocalBeanRepository` → `Vector.isEmpty` | 7 samples (`ConcurrentHashMap$Node`) |

The cpu event samples only threads that are on the CPU. With the same 8
threads and duration, the groovy run has a third fewer samples than the Java run because the threads are parked on the
registry monitor. The on-CPU groovy threads spend 29% waiting, spinning or waking on that monitor. The `findByType`
at `GroovyExpression.java:71` (finding 1) is the only lock in the groovy route.

### Allocation profiles (JDK 21, async-profiler `event=alloc`)

Same runs and layout as above, in `raw/flamegraphs-collapsed/alloc/…`. async-profiler samples allocations by
allocated bytes (TLAB refills and outside-TLAB allocations), so the shares are approximately shares of allocated bytes.
The line numbers are main before the prototype commits (`34f04c13fe59^`).

**groovy vs Java concat expression (scenario 1, alloc):**

| | groovy (86,052 samples) | Java `Expression` (49,133 samples) |
|---|---|---|
| binding | **`createBinding` 78.0%**: `populateVariableMap` `HashMap$Node` 26.5%, **`ExchangePropertyKey[]` 18.8%**, `HashMap$Node[]` 6.5%, `FlatMap` entry-set iterators ~4%; `HashMap.put` resizes 13.4%; `Binding` 1.5%, `DefaultAttachmentMessage` 1.0% | — |
| script instance | **`instantiateScript` 12.2%**: **`Constructor` copy 4.6%** (`Class.getDeclaredConstructor`), `WeakReference` 1.9% (`Constructor.newInstanceWithCaller`), `Binding` 1.6% (the script's default binding), the `Script` object 1.5%, `resolveLanguage` lambda 1.5% | — |
| script body | `StringGroovyMethods.plus` 6.7% | the result `String` + `byte[]`, 100% |

- **The `ExchangePropertyKey[]` (18.8%) is the `ExchangePropertyKey.values()` clone** in
  `AbstractExchange.getInternalProperties()` (`core/camel-support/.../AbstractExchange.java:1026`). It runs on every
  `getAllProperties()` call, which `ExchangeHelper.populateVariableMap` makes for the `exchangeProperty` /
  `exchangeProperties` variables (`ExchangeHelper.java:511`). The copied map itself is part of the `HashMap` shares.
  This is a camel-core cost that every language calling `populateVariableMap(…, true)` pays. A cached
  `static final ExchangePropertyKey[]` would remove the array, but not the map copy. Only the binding change
  (finding 2) avoids both.
- **`ObjectHelper.newInstance(Class, Class)` (`ObjectHelper.java:582`, called from `GroovyExpression.java:91`) copies
  the `Constructor` on every evaluation.** `getDeclaredConstructor()` returns a fresh copy each time. Together with the
  script's own default `Binding` (created in `Script.<init>` and replaced at `GroovyExpression.java:60`), that is
  ~6% of the bytes (finding 7). The benchmark-local `OptimizedGroovyExpression` avoids the copy with a cached
  `MethodHandle`. The camel-groovy prototype (section 9) still calls `ObjectHelper.newInstance`.

**groovy vs Java route, 1 thread (scenario 4, alloc):**

| | groovy route (54,804 samples) | Java route (40,282 samples) |
|---|---|---|
| route logic | **`GroovyExpression.evaluate` 67.4%**: `createBinding` 54.9% (`ExchangePropertyKey[]` 12.6%), `instantiateScript` 8.3%, script body ~2.3% | Java lambdas 3.6% |
| top self | `HashMap$Node` 20.5%, `HashMap$Node[]` 13.2%, `ExchangePropertyKey[]` 12.6%, `Object[]` 9.9%, `HashMap` 6.0%, `Constructor` 3.2% | `Object[]` 27.5%, `int[]` 9.7%, `CamelInternalProcessor$AsyncAfterTask` 8.4%, `DefaultExchange` 7.5%, `RedeliveryErrorHandler$SimpleTask` 5.9%, `EnumMap` 5.1%, `Pipeline$PipelineTask` 4.2%, `DefaultUnitOfWork` 4.1% |

In the Java route almost all allocation is Camel's per-exchange engine objects. **In the groovy route two thirds of
all allocated bytes are the two groovy evaluations**, 80% of that the binding maps. This matches the `-prof gc` numbers
of scenario 4 and the allocation rates of the load test (section 5).

**groovyJson `marshal`, `prettyPrint=true` (scenario 7a, alloc):**

| | 1 KB (100,719 samples) | 1 MB (75,014 samples) |
|---|---|---|
| inclusive | `JsonOutput.prettyPrint` 65.5% (`char[]` 41.0%, `byte[]` 6.1%, `int[]` 4.6%, `String` 4.1%, `JsonToken` 3.4%, `Matcher` 3.2%); **`DefaultJsonGenerator.toJson` → `AtomicReference` 18.6% + `AtomicReference[]` 9.7%** | `JsonOutput.prettyPrint` 93.9% (`JsonLexer.nextToken` 90.9%) |
| top self | `char[]` 42.2%, `AtomicReference` 18.6%, `AtomicReference[]` 9.7%, `byte[]` 8.0% | `char[]` 57.4%, `byte[]` 9.9%, `int[]` 7.5%, `String` 6.5%, `JsonToken` 5.3%, `Matcher` 5.1% |

- **At 1 KB, 28% of the bytes are a new cache per marshal call.** The stack is `DefaultJsonGenerator.writeNumber` →
  `CharBuf.addDouble` → `new SimpleCache` → `CommonCache` → `ConcurrentLinkedHashMap.<init>`. The bytecode of
  `org.apache.groovy.json.internal.CharBuf` (groovy-json 5.1.2) creates its `dcache` field lazily on the first
  `double`. `JsonOutput.toJson` creates a new `CharBuf` per call, so every document with a `double` (here the
  `price` values) builds and discards a `ConcurrentLinkedHashMap`. This is the `ConcurrentLinkedHashMap.<init>` 12%
  of the cpu profile. It is inside Groovy (an upstream observation, not a camel-groovy bug). At 1 MB it is a one-off
  and disappears.
- **The rest is `prettyPrint` re-lexing the generated text:** char buffers, tokens and regex matchers. This is the
  243 MB per 1 MB document of scenario 7a.

**groovyXml `unmarshal` and `Map` `marshal` (scenario 7b, alloc):**

| | 1 KB | 1 MB |
|---|---|---|
| unmarshal | **`XmlParser.<init>` 64.1%** (36,240 samples), of which **`XmlUtil.setFeatureQuietly` 29.9%**: each `SAXParserFactoryImpl.setFeature` builds a throwaway `SAXParserImpl` (`newSAXParserImpl`) to validate the feature; the real `newSAXParser` ~19% | `XmlParser.parse` 99.8% (34,547 samples): `byte[]` 26.9%, `LinkedHashMap` 15.3%, `Object[]` 13.9%, `String` 13.1%, `StringBuilder` 11.5%, `groovy.util.Node` 7.4%, `NodeList` 5.7% |
| marshal `Map` | `printLines` 62.7% (63,671 samples): **`String.getBytes` 27.2%**, `ByteArrayOutputStream` growth 16.2%, `StringHelper.padString` 9.8%; `doSerialize` 32.5% (`Line` 8.0%, `LinkedHashMap` 6.2%) | `printLines` 62.0% (48,772 samples), `padString` 11.6%; `doSerialize` 36.0% |

- **The parser setup allocates more than the 1 KB document parse.** `new XmlParser()` per unmarshal allocates 64% of
  the bytes. Half of that is the JDK's `SAXParserFactoryImpl.setFeature`, which creates a complete parser for each
  feature Groovy sets, only to check that the feature is supported. A parser (or at least a configured
  `SAXParserFactory`) reused per data format instance would remove the lookup (cpu), the throwaway parsers and the real
  parser (scenario 7b). `XmlParser` is not thread-safe, so reuse needs a pool or a thread-local.
- **Marshal allocates one `byte[]` per written fragment** (`String.getBytes`) plus an indent `String` per line
  (`padString`). The `ByteArrayOutputStream` growth share is the benchmark's in-memory sink. A real stream would not
  grow, but it would get one unbuffered `write` per fragment (the 28–34× of scenario 7b).

## 7. Findings (ranked)

The IDs are stable, because the rest of the report cites them. The rows are ordered by end-to-end impact on a route.
Line numbers are for `e1d8cc6fee92`, the measured `main`. "Prototype" is the camel-groovy change of section 9
(local, not pushed).

### Confirmed by data

| ID | Finding | Where | Evidence (full runs) | Fix and prototype result | Risk | API / upgrade guide |
|---|---|---|---|---|---|---|
| 1 | Every evaluation calls `resolveLanguage("groovy")` and `registry.findByType(GroovyShellFactory.class)`. That scans every registry bean and takes the synchronized `DefaultRegistry` `Stack` monitor (`Vector.isEmpty`) | `GroovyExpression.java:70-71` | 500 unrelated beans: 3.36 M → 0.28 M ops/s (11.8× slower). 8-thread JMH route: groovy 1.37 M vs Java 6.32 M msg/s, and 100% of the lock samples are on that monitor. 5 min load: groovy 1.08 M vs Java 4.11 M msg/s at 46% CPU, p99 102 µs | Resolve once per `CamelContext`. Prototype: 12.2–12.5 M ops/s with or without 500 beans; 8-thread route 3.83× (0.83× Java); load 3.45× (0.91× Java), p99 3 µs, 79% CPU | A `GroovyShellFactory` bound after the first evaluation is ignored | Behaviour change for late-bound factories: upgrade-guide note |
| 2 | The binding is rebuilt on every evaluation: a globals `HashMap`, a second `HashMap` copy, `populateVariableMap` (copies all exchange properties through `getAllProperties()`, which forces an `ExchangeVariableRepository`), a `DefaultAttachmentMessage` and a `Binding` | `GroovyExpression.java:58-60,94-105`, `ExchangeHelper.java:498-524`, `AbstractExchange.java:378-385,1024-1033` | Step benchmark: ~158 ns / 1,152 B (including the 48 B argument map) of a ~297 ns evaluation. Allocation profile: `createBinding` is 78% of the bytes of a groovy expression and 55% of a groovy route's | Lazy `ExchangeBinding` (snapshot of `in`/`body`/`headers`/`exception`/`out`, lazy properties, variables and attachments). Prototype: expressions 3.4–5.3× faster, 1,336–1,568 → 272–384 B/op; 1-thread route 1.69×, 4.7 → 2.2 KB/msg | `exchangeProperties` and `variables` are read on first access instead of at binding creation (14 new tests cover the semantics); subclasses that override `createBinding` | Protected method behaviour: upgrade-guide note |
| 3 | The script cache evicts in **insertion order**, not LRU (`SimpleLRUCache.get` does not record access). With more than 1,000 distinct scripts every evaluation recompiles | `GroovyLanguage.java:69`, `SimpleLRUCache.java:140` | Round robin over 1,001 scripts: 0.70 ms and 480 KB per evaluation, one class loaded and one unloaded per evaluation (100 scripts: 479 ns). A hot script is recompiled after 1,000 cold ones (churn harness). With `-XX:SoftRefLRUPolicyMSPerMB=0`, 36% of evaluations recompile even with 1,000 scripts. 5 min load with 1,500 scripts: 5,019 msg/s, 600,847 classes loaded in 4 min, 7.6% GC pause time (mixed + remark), 570 MB live heap | Keep the compiled class in the expression. Prototype: 1,001 scripts 8.4 µs (84×); load with 1,500 scripts 2.73 M msg/s (544×), no class churn, flat 110 MB heap | An expression keeps its class as long as the route lives; dev reload must drop it (generation counter in the prototype); expressions created per use still go through the FIFO cache | No API change; the eviction order is core (below) |
| 5 | `groovyJson` with `prettyPrint=true` (the default) serializes to a `String`, then re-lexes and re-serializes it | `GroovyJSonlDataFormat.java:36,77-80` | Marshal 1 KB: 60.8 µs vs Jackson 1.9 µs (32×), 352 KB. 1 MB: 55.6 ms (30×), 243 MB. 75–84% of the cpu is in `JsonOutput.prettyPrint` (regex-based lexer) | Not prototyped: indent while generating. `prettyPrint=false` is 13.5 µs (7× Jackson) | The pretty output must stay identical or the change must be documented | Changing the default or the output needs an upgrade-guide entry |
| 9 | `groovyXml` unmarshal creates a new `XmlParser` for every call: `SAXParserFactory` lookup on the class path plus feature setup | `GroovyXmlDataFormat.java:81` | 1 KB: 33.2 µs vs 18.3 µs with a cached factory (1.8×). cpu: 61% in `XmlParser.<init>`. Allocation: 64% of the bytes, half of them the JDK building a throwaway parser in every `setFeature`. 1 MB: no difference | Not prototyped: keep a configured factory or parser per thread (JAXP factories and `XmlParser` are not thread-safe) | Must keep the parser features Groovy's constructor sets (XXE hardening, see `design/security.adoc`) | No |
| 10 | `groovyXml` `Map` marshal calls `String.getBytes()` and `os.write` once per fragment, and runs the `TypeConverter` on every value | `GroovyXmlDataFormat.java:97-138,154,196` | 1 KB 7.4 µs vs jacksonXml 3.0 µs; 1 MB 9.4 ms vs 3.1 ms (2.5–3×); 4–5× the bytes (the documents differ slightly). On an unbuffered `FileOutputStream`: 252 µs (34×) and 261 ms (28×). ~70% of the cpu is in `printLines` | Not prototyped: one buffered `Writer` | The Marshal EIP already writes to a buffered `OutputStreamBuilder`; the 28–34× only hits direct `DataFormat.marshal` callers | No |
| 6 | Groovy closures over collections allocate per element, even with `@CompileStatic` or pre-compiled classes. `DefaultGroovyMethods.any` calls `Closure.call` per element (argument array, `BooleanClosureWrapper`, boxing). This is the Groovy runtime, not camel-groovy | Groovy `DefaultGroovyMethods.any` | Groovy 5.1.2: ~72 KB per evaluation over 1,000 items and ~11× Java streams for every Groovy variant. Groovy 6.0.0-RC-1: 5.2–6.8× faster at 1,000 items (~0.6× Java) and 1.46–1.74× at 10 items (section 10) | Track the Groovy 6 upgrade (release candidate; the earlier review found Spock blocks it in Camel's build, not re-checked) | - | Groovy major upgrade: upgrade guide |
| 11 | Many distinct scripts that each run rarely stay in C1 tier-3 code, where invokedynamic call-site chains are not inlined | Groovy invokedynamic + HotSpot tiering, exposed by one class per expression | 1,000 cached scripts in round robin: 3.3 µs rising to a ~14.5–15 µs plateau (~28× 100 scripts), with no class loading. 93.7 MB of tier-3 code vs 1.9 MB of C2 code. No deoptimization storm (142 vs 119). ~58% of the cpu in `script.run()` walking method-handle chains. The prototype does not change it. With 900 scripts at ~260 runs per second each, the load route recovers after a 15–25 s warm-up dip | Not tested: a `@CompileStatic` shell factory, `-XX:-TieredCompilation` | The symptom is confirmed. Profile and code cache strongly indicate the mechanism, but it is not proven | A static compilation option would be a new documented option |
| 4 | Concurrent cache misses compile the same script once per thread | `GroovyExpression.java:80-88` | Churn harness: 8 threads give 8.00 compilations per new script (50 trials) | Not in the prototype: compile under `computeIfAbsent` semantics | First use only | No |
| 7 | Reflective `Script` instantiation: `getDeclaredConstructor()` copies the `Constructor` on every evaluation, and `Script.<init>` creates a default `Binding` that is replaced immediately | `GroovyExpression.java:91` → `ObjectHelper.java:582`; `GroovyExpression.java:60` | Step benchmark: 28 ns / 152 B vs 13 ns / 48 B with a cached `MethodHandle`. Allocation profile: `Constructor` 4.6% + `WeakReference` 1.9% + default `Binding` 1.6% of a groovy expression's bytes | Not in the camel-groovy prototype, which is ~26 ns / 136 B behind the benchmark-local variant with a `MethodHandle` | None. Do not pool `Script` instances: each holds its `Binding` | No |
| 8 | Per evaluation: `resolveLanguage("groovy")` ~7 ns, and the `fileName + text` cache key ~19 ns / 88 B | `GroovyExpression.java:70,79` | Step benchmark | Removed by the prototype (resolved per context; key only built on a miss) | None | No |

### Camel core side findings

- **`DefaultRegistry.localRepository` is a synchronized `java.util.Stack`** (`DefaultRegistry.java:60,115-120`),
  read on every `lookupByName` / `findByType`. Before CAMEL-21675 (Camel 4.10, `557b7ff166a7`) the hot path was a
  lock-free `volatile boolean` check plus a `ThreadLocal`. Any runtime registry lookup under concurrency pays this
  monitor, not only groovy; it is the only lock in the 8-thread groovy route (section 6). A lock-free structure
  (`ConcurrentLinkedDeque`, or a volatile fast-path flag) would keep nested kamelets working. The change also made
  local beans visible across threads (they were thread-local), which is worth a separate look.
- **`AbstractExchange.getInternalProperties()` clones `ExchangePropertyKey.values()` on every call**
  (`AbstractExchange.java:1026`). `getAllProperties()` calls it from `ExchangeHelper.populateVariableMap(…, true)`
  (`ExchangeHelper.java:511`). The clone is 18.8% of the bytes of a groovy expression and 12.6% of a groovy route's.
  Every language that builds its variables through `populateVariableMap` pays it. A cached `static final` array
  removes the clone, but not the map copy.
- **`SimpleLRUCache` is FIFO by insertion despite its name** (`SimpleLRUCache.java:140`: `get` does not record
  access). `DefaultLRUCacheFactory` is the only implementation in the tree, so every `LRUCacheFactory` user (simple,
  jactl, groovy) evicts that way. This is a core JIRA candidate.

### Upstream observations (Groovy, JDK)

- **Groovy `JsonOutput.toJson` builds a number cache per call.** It creates a new `CharBuf`, which lazily creates a
  `SimpleCache` (a `ConcurrentLinkedHashMap`) when it writes the first `double`. That is 28% of the bytes and ~12% of
  the cpu of a 1 KB `groovyJson` marshal (groovy-json 5.1.2 bytecode, section 6).
- **The JDK's `SAXParserFactoryImpl.setFeature` builds a complete `SAXParserImpl` to validate each feature.** That is
  ~30% of the bytes of a 1 KB `groovyXml` unmarshal (JDK 21, section 6).

### Side findings in other languages (found while building the comparison)

- **camel-joor:** a script that uses the same helper twice, e.g.
  `'order-' + headerAs('amount', Integer) + '-' + headerAs('vip', Boolean)`, does not compile
  (`cannot find symbol: variable Integer`). The generated source is
  `headerAs(message, "amount",  Integer) + "-" + headerAs(message, "vip", Boolean.class)`: the pattern for the
  three-argument `headerAs(name, defaultValue, type)` form uses a greedy `(.+)` and matches across both calls
  (`JoorCompiler.java:48-51`; the same greedy `(.+)` is in `EXCHANGE_PROPERTY_AS_DEFAULT_VALUE_PATTERN`, `:58-63`, and
  `[A-Za-z0-9.$]*.class` has an unescaped `.`). Workaround: write `Integer.class`.
- **camel-javascript:** every evaluation creates a new GraalJS `Context` (with its own engine) and rebuilds the
  `Source` (`JavaScriptExpression.java`, `JavaScriptHelper.newContext`), so nothing is cached between evaluations.
- **camel-python3:** one shared GraalPy `Engine`, but a new `Context` per evaluation
  (`Python3Language.evaluateExpression`).
- **GraalVM runtime mode:** with the polyglot jars on the class path of a stock JDK 21 the engine reports
  `Interpreted` (no Truffle optimizing compiler); camel-javascript/camel-python3 also set
  `engine.WarnInterpreterOnly=false`, so users are not told.
- **camel-python (Jython):** one `PythonInterpreter` per expression whose globals are set on every evaluation;
  suspected not thread safe under concurrent evaluation (not measured, not included in the comparison).
- **camel-jactl:** same insertion-order `LRUSoftCache` as groovy, and concurrent first use can compile a script twice
  (documented in `JactlLanguage.getScript`).

### Suspected, not measured

- **`GroovyLanguage.evaluate` creates a `GroovyShell` per cache miss** (`GroovyLanguage.java:158-163`). It is only
  used when script beans are created (startup), so low impact is expected.
- **With Spring, finding 1 is likely worse.** `findByType` goes through
  `BeanFactoryUtils.beansOfTypeIncludingAncestors` on every evaluation. The prototype removes the per-evaluation
  lookup either way.
- **`DefaultGroovyScriptCompiler`:** the startup compile cost and `preloadCompiled` were not measured.
- **`@CompileStatic`** was not measured for plain property access, arithmetic and string concatenation, nor for the
  many-scripts case of finding 11, where it is the most likely mitigation.
- **`CompilerConfiguration` tuning:** Groovy 5 always uses invokedynamic, and there is no obvious knob.

### Method notes (including the independent review)

- **Load runs are compared over the 60–300 s window.** The tails of the 10-minute runs (p99.9, max pause, full-GC
  counts) are not comparable with 5-minute runs.
- **`smoke/GroovyScriptCacheChurnTest.txt` is not cited** (`classesUnloaded=+0`). That harness version kept every
  script class strongly reachable. The churn figures come from the `churn` phase output.
- **Soft references:** with the default `SoftRefLRUPolicyMSPerMB` the churn harness cannot observe clearing on a
  mostly empty heap. The `-XX:SoftRefLRUPolicyMSPerMB=0` run shows what the soft cache does under memory pressure.
- **`stepCreateBinding`** includes the `new HashMap<>()` argument (48 B) in its 1,152 B / 158 ns.
- **`simpleArithmetic`** computes `sum(body, body, 1)`: the same result with a different operator.
- **Load harness CPU** is sampled as a fraction of the 10 logical CPUs (8 performance + 2 efficiency cores).
- **`GroovyFirstEvaluationTest`** uses `@Setup(Level.Invocation)` with a full CamelContext start, which is fine in
  SingleShotTime.
- **The Stack-based `DefaultRegistry`** costs a monitor enter on every registry lookup even when uncontended (no
  biased locking since JDK 15), for every component that looks up beans at runtime.
- **Background load:** macOS processes (Spotlight, `mediaanalysisd`, `signpost_reporter`, a browser tab) overlapped
  some runs. Each affected section says which runs.

## 8. apache/camel#26260 (CAMEL-24669)

The PR changes `groovyJson` `prettyPrint=false` from double-encoding to plain `JsonOutput.toJson` and adds Jackson 3
node detection. It does not touch the pretty-print path or the XML serializer. `marshalJsonOutputToJson` models the
fixed compact path.

## 9. Prototype

Local branch `camel-groovy-perf-review` in apache/camel, not pushed. Commits `34f04c13fe59` and `565c7f6d95d4`, which
fixes the findings of the independent review:

- The language and the `GroovyShellFactory` are resolved once per `CamelContext`, not once per evaluation (finding 1).
- The compiled script class is kept per expression, checked against the context and the language, and invalidated
  by a generation counter on language `stop()` or dev-mode reload (finding 8). The shared script cache no longer
  calls `removeClass` on eviction (`stopOnEviction=false`), so an evicted class that an expression still holds keeps
  working.
- `ExchangeBinding` (finding 2) takes a snapshot of `in`, `body`, `headers`, `exception` and `out` when the binding is
  created. It creates `exchangeProperties`, `variables` and `attachments` lazily, once per evaluation, and
  `getVariables()` materializes the full map from the snapshot. The globals map passed to subclasses stays mutable.
- Not changed: reflective `Script` instantiation (finding 7), cache eviction order (finding 3), duplicate compilation
  on concurrent misses (finding 4), and the data formats.

Tests: `mvn test` in `components/camel-groovy` on `565c7f6d95d4` ran 72 tests (27 classes), with 0 failures, 0 errors
and 1 skipped (`GroovySetHeaderConcurrentIssueTest`, `@Disabled` on main). The 72 include 14 new tests in `GroovyExpressionBindingTest`, which covers variable
names, snapshot semantics, `removeVariable`, script writes, attachments, subclass globals, shell factories and cache
invalidation.

The prototype is installed as `org.apache.camel:camel-groovy:4.23.0-perf-SNAPSHOT` by `install-prototype.sh`, and
the benchmarks select it with `-Dcamel-groovy-bench-version=4.23.0-perf-SNAPSHOT`. Everything else (camel-core,
Groovy 5.1.2, JDK 21, JMH settings) is the same as the baseline runs.

**Expression and predicate (scenarios 1–2, thrpt, `GroovyExpressionTest-jdk21-prototype.jmh.json` vs
`GroovyExpressionTest-jdk21.jmh.json`):**

| benchmark | before ops/s | after ops/s | speed-up | before B/op | after B/op |
|---|---|---|---|---|---|
| `concatGroovy` `body + '-' + header.foo` | 3,001,362 ± 33,509 | 10,228,515 ± 114,625 | **3.41×** | 1,568 | 384 |
| `arithmeticGroovy` `body * 2 + 1` | 3,656,819 ± 86,337 | 19,382,188 ± 209,921 | **5.30×** | 1,336 | 272 |
| `predicateGroovy` `headers.amount > 100` | 3,623,062 ± 23,970 | 17,838,627 ± 92,928 | **4.92×** | 1,344 | 280 |

**Collection logic, "any line item > 100" (scenario 3, thrpt, `GroovyCollectionTest-jdk21-prototype.jmh.json`):**

| benchmark | size | before ops/s | after ops/s | ratio | before B/op | after B/op |
|---|---|---|---|---|---|---|
| `groovyDynamic` | 10 | 1,722,843 ± 10,232 | 2,436,003 ± 119,511 | **1.41×** | 2,528 | 1,456 |
| `groovyCompileStatic` | 10 | 1,513,159 ± 22,879 | 2,483,020 ± 9,767 | **1.64×** | 3,024 | 1,488 |
| `groovyDynamic` | 1000 | 16,831 ± 535 | 16,225 ± 156 | 0.96× | 73,849 | 72,745 |
| `groovyCompileStatic` | 1000 | 17,196 ± 360 | 16,674 ± 174 | 0.97× | 74,305 | 72,777 |

With 10 items the prototype saves the same ~1.1–1.5 KB of per-evaluation overhead as in scenarios 1–2. With 1,000
items the closure over the list dominates, ~72 KB and ~60 µs per evaluation (finding 6), and the prototype does not
touch it: allocation drops by ~1.1–1.5 KB (1.5–2%). Throughput is 3–4% lower, just outside the JMH error bars.
**That is run-to-run variance, not a regression.** The groovy6 phase re-ran the same benchmarks with camel-groovy from
main and Groovy 5.1.2 at 18:57–19:10 (`GroovyExpressionTest-jdk21-groovy-5.1.2.jmh.json`, without `-prof gc`).
Against the 16:40 baseline, `groovyDynamic` size=1000 came out at 0.96× (16,831 → 16,074 ops/s) with no code change,
and `groovyCompileStatic` size=1000 at 1.16× (17,196 → 19,940 ± 4,936). In the same repeat the expression, size=10
and route benchmarks stayed within 0.97–1.04× of the baseline. Differences of a few percent at size=1000 are
therefore noise, and only the larger ratios in this section are effects of the prototype.

**Full route, end to end (scenario 4, thrpt, `GroovyRouteTest-jdk21-prototype.jmh.json`, same settings: 2 forks,
5 × 2 s warmup, 5 × 2 s measurement):**

| benchmark | before msg/s | after msg/s | speed-up | before B/msg | after B/msg | Java route msg/s (B/msg) | groovy / Java before → after |
|---|---|---|---|---|---|---|---|
| `groovyRoute1Thread` | 652,420 ± 3,466 | 1,099,633 ± 7,374 | **1.69×** | 4,664 | 2,216 | 1,352,257 ± 9,711 (1,560) | 0.48 → **0.81** |
| `groovyRoute8Threads` | 1,374,665 ± 14,398 | 5,267,328 ± 492,093 | **3.83×** | 4,704 | 2,144 | 6,321,578 ± 668,119 (1,536) | 0.22 → **0.83** |

- **The 8-thread route now scales like the Java route.** With 8 threads it runs 4.8× its single-thread rate; the Java
  route runs 4.7×. Before the prototype, groovy managed 2.1×. Removing the per-evaluation `findByType` removes the
  only lock (section 6), so the 4.6× gap to Java becomes 1.2×.
- **Allocation per message halves** (4.7 KB → 2.2 KB). ~0.6 KB per message remains above the Java route. The
  prototype was not profiled. From the code, that should be the two script instances, the two `ExchangeBinding`s
  and the script bodies' own objects, but this is not measured.
- The 8-thread error bars are ~9% on both the groovy and the Java route. The machine has 10 cores (8 performance +
  2 efficiency), so 8 benchmark threads plus Camel and the JVM's own threads are sensitive to background load.
- The route latency run (`-sample`) was not repeated with the prototype. Section 5's load runs cover latency under
  load.

**Evaluation overhead, `body + '-' + header.foo` (scenario 6, thrpt, `GroovyOverheadTest-jdk21-prototype.jmh.json`):**

| extra registry beans | `GroovyShellFactory` bean | before ops/s | after ops/s | speed-up | before B/op | after B/op |
|---|---|---|---|---|---|---|
| 0 | none | 3,362,248 ± 19,360 | 12,189,631 ± 257,927 | **3.63×** | 1,400 | 384 |
| 0 | with `getFileName` | 2,552,970 ± 20,817 | 12,357,070 ± 49,682 | **4.84×** | 2,000 | 384 |
| 500 | none | 283,929 ± 982 | 12,180,777 ± 18,912 | **42.9×** | 1,480 | 384 |
| 500 | with `getFileName` | 177,819 ± 3,344 | 12,452,648 ± 80,033 | **70.0×** | 2,000 | 384 |

For comparison, the benchmark-local prototypes from the baseline run, which never call `findByType` either:
`evaluatePrototypeOptimized` (eager binding) ran 5.71–5.73 M ops/s at 1,160 B, and `evaluatePrototypeLazyBinding`
ran 18.10–18.25 M ops/s at 248 B, in all four configurations.

- **The cost no longer depends on the registry or the shell factory.** All four configurations run 12.2–12.5 M ops/s
  (~81 ns) with 384 B. Before, 500 unrelated beans made an evaluation 11.8–14.4× slower. A shell factory added
  0.6 KB, and 32% more time per evaluation with 0 beans or 60% (+2.1 µs) with 500. With a factory, each evaluation
  of the original code also called `getFileName` and `getVariables`, copied the variables into the globals map (and
  again into the binding), and built the cache key `fileName + text` (`GroovyExpression.java:74-79`). That explains
  the extra 0.6 KB. It does not obviously explain +2.1 µs with 500 beans, which is not broken down. The prototype
  still calls `getFileName` and `getVariables` on every evaluation (they take the exchange;
  prototype `GroovyExpression.java:88-89`). It no longer looks the factory up in the registry, and it builds the
  key only when the class kept by the expression does not match the context, language, generation and file name
  (lines 95-101).
  With this benchmark's cheap factory, the four configurations are equal.
- **The camel-groovy prototype is ~26 ns and 136 B behind the benchmark-local lazy binding.** It still creates the
  script through `ObjectHelper.newInstance` (finding 7: ~15 ns and ~104 B more than a `MethodHandle` in the step
  benchmark), and its `ExchangeBinding` keeps a snapshot of five fields. The rest of the gap has not been broken
  down.

**Round robin over N distinct scripts (scenario 5c, avgt, `GroovyScriptCacheTest-jdk21-prototype.jmh.json`, 2 forks,
5 × 2 s warmup, 5 × 2 s measurement, `-prof gc` and `-prof cl`):**

The benchmark creates one `Expression` per distinct script at setup and evaluates them in turn. This is how a route
uses its expressions: they are created once, when the route is built.

| distinct scripts | before µs/op | after µs/op | ratio | before B/op | after B/op | classes loaded per op, before → after |
|---|---|---|---|---|---|---|
| 100 | 0.48 ± 0.00 | 0.15 ± 0.00 | **3.2×** | 1,448 | 384 | 0 → 0 |
| 1000 | 7.48 ± 4.89 | 8.57 ± 4.63 | *(see below)* | 1,697 | 553 | 0 → 0 |
| 1001 | 702.73 ± 39.07 | 8.41 ± 4.66 | **83.6×** | 480,514 | 577 | 1.0 → 0 |
| 2000 | 699.56 ± 41.52 | 3.29 ± 0.49 | **212×** | 480,777 | 607 | 1.0 → 0 |

- **Past 1,000 scripts the recompilation is gone.** Before, every evaluation recompiled its script (0.70 ms, 480 KB,
  one class loaded and one unloaded per operation; finding 3). The prototype keeps the class in the expression, so a
  script evicted from the shared cache (still FIFO, still 1,000 entries) is not compiled again. It stays reachable
  through the expression, and the cache no longer calls `removeClass` on eviction. Evaluations that create a new
  `Expression` for each use still go through the shared cache and still hit finding 3. Examples are
  script text computed at runtime, `language:groovy:` endpoints with dynamic resources, and the
  `compileDistinctScripts` shape. The prototype does not change the cache itself.
- **1,000 scripts: no conclusion from this run.** Both runs are on the same rising curve: baseline 3.0 → 11.4 µs and
  prototype 3.9 → 12.0 µs over the five iterations of each fork, hence the ±60% error. This is the JIT effect of
  section 4, scenario 5b/5c (many script classes, each run rarely, left in tier-3 profiled code with un-inlined
  invokedynamic chains). In the 20-iteration run it levels off at ~13–15 µs. It is not a cache effect, and the
  prototype was not expected to change it. The 0.87× is two points on a ramp, not a regression. The 1,001-script
  prototype run shows the same ramp (3.5 → 11.8 µs).
- **2,000 scripts at 3.3 µs is probably the same ramp, starting later.** Each script runs half as often as with
  1,000, and the raw iterations rise slowly (2.9 → 3.4 µs and 3.0 → 3.4 µs after the first iteration). This is a
  hypothesis: a longer run would show whether it also levels off at ~13–15 µs.
- Allocation grows from 384 B (100 scripts) to 553–607 B (1,000–2,000). This is not broken down. One plausible
  cause is the profiled tier-3 code allocating what C2 would scalar-replace.

**Long running load, 8 producer threads, unbounded rate, 5 min, `-Xms1g -Xmx1g` (section 5 route: filter + vip check +
body, steady state 60–300 s; `GroovyLoadTest-groovy-prototype.*`, `groovy-prototype-gc.log`):**

The first three rows ran back to back at 18:47–19:48 with the same harness (`a515a5f`) and the same benchmark
classpath. The last two are the original 13:36/13:46 baselines, which used an older harness and classpath (see below).

| variant | msg/s | p99 µs (median/max) | bytes/msg | alloc MB/s | GC pauses/s | pause % (GC log) | max pause ms | heap after young GC MB | CPU % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| java (19:37, `-harness2`) | 4,109,230 | 2 / 2 | 1,538 | 6,027 | 9.89 | 1.01 | 1.68 | 17.0 | 79.7 |
| groovy, camel-groovy main (19:42, `-harness2`) | 1,082,957 | 102 / 103 | 5,598 | 5,781 | 9.49 | 0.99 | 1.26 | 25.9 → 26.0 | 45.9 |
| **groovy, camel-groovy prototype (18:47)** | **3,737,215** | **3 / 4** | 3,002 | 10,698 | 17.57 | 1.84 | 1.58 | 26.0 → 26.0 | 78.8 |
| *java (13:36, older harness)* | *3,958,295* | *2 / 4* | *1,538* | *5,805* | *9.52* | *0.97* | *4.97* | *10.0* | *79.6* |
| *groovy, main (13:46, older harness)* | *1,053,471* | *105 / 109* | *5,566* | *5,592* | *9.16* | *0.94* | *1.77* | *18.0 → 18.2* | *46.5* |

- **3.45× the throughput of groovy on main, and 0.91× the Java route.** p99 drops from 102 µs to 3 µs, and CPU use
  rises from 46% to 79% because the producer threads no longer wait on the registry lock. The benchmark-local
  prototype of section 5 (3.72 M msg/s, 13:56, older harness) lands in the same place.
- **The heap stays flat, and the prototype retains no extra memory.** Heap after young GC is 26.0 MB for the
  prototype and 25.9–26.0 MB for groovy on main, flat from the first to the last third. Neither run has mixed or full
  collections or class loading, and metaspace is 28.4–28.6 MB in both. The prototype allocates ~1.9× the bytes per
  second because it handles 3.45× the messages; per message it allocates 46% less (3,002 vs 5,598 B). The young GC
  rate follows the allocation rate (17.6/s vs 9.5/s), and pauses stay short (1.84% of wall time, max 1.58 ms).
- **The re-run changed the baselines by a few percent.** On the current harness java measures +3.8% (4.11 M vs
  3.96 M msg/s) and groovy on main +2.8% (1.08 M vs 1.05 M), with the same bytes per message. The harness fix gave
  each producer thread its own latency histogram instead of one `AtomicLongArray` shared by all 8, and the shared one
  cost a few percent at these rates. Against the older baselines the prototype had looked like 3.55× groovy and
  0.94× java.
- **The heap after young GC moved from 10 / 18 MB to 17 / 26 MB with the benchmark classpath, not with camel-groovy.**
  Every load run since commit `d89d866` (14:49) shows 5 humongous regions (5 MB) plus ~2 old regions from the first
  GC at 0.4 s, before any load. That commit added camel-jactl, camel-mvel, camel-javascript and camel-python3 to the
  benchmark classpath. The affected runs include java (`java-harness2-gc.log`), groovy on main, the prototype, jactl
  and the 900-script run. The 13:36/13:46 runs predate the commit and have none. What allocates them was not
  investigated.
- The tail of a macOS `signpost_reporter` burst (~80% of a core, ~19:28 to ~19:39) overlapped the first ~2 minutes of
  the java re-run. Its 5-second throughput samples stay within 4.10–4.13 M msg/s from 10 s on, with no visible dip.

**Long running load with many distinct scripts (`groovyManyScripts`: `setBody` picks one of `load.scripts` distinct
scripts per message; same route, threads and heap, steady state 60–300 s):**

| run | distinct scripts | camel-groovy | msg/s | p99 µs (median/max) | bytes/msg | pause % (GC log) | max pause ms | heap after young GC MB | metaspace MB | classes loaded / unloaded in window |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `groovyManyScripts` (14:06, older harness) | 1,500 | main | 5,019 | 5,550 / 8,500 | 233,579 | 7.63 (young 7.4 s, mixed 5.1 s, remark 5.7 s, 1 full) | 69.9 | 569 → 570 | 62.8 → 77.6 | 600,847 / 597,013 |
| `groovyManyScripts-900scripts` (18:25) | 900 | main | 933,913 | 98 / 99 | 5,542 | 1.00 | 1.54 | 76 | 65.4 → 65.5 | 0 / 0 |
| **`groovyManyScripts-prototype` (18:52)** | **1,500** | **prototype** | **2,732,130** | **6 / 11** | 3,058 | 1.85 (young only) | 2.21 | 110 → 110 | 88.5 → 88.7 | 2 / 0 |

- **With 1,500 scripts the prototype handles 544× the messages of main**, and the heap stops churning. On main,
  every evaluation of a script evicted from the 1,000-entry cache compiles it again: 600,000 classes loaded and
  unloaded in 4 minutes, 234 KB per message, mixed and remark collections, 7.6% pause time and a 570 MB live heap.
  With the prototype each route's `Expression` keeps its class, so after warm-up nothing is compiled again (2 classes
  loaded in the window). The heap after young GC is flat at 110 MB, and only young collections run (1.85% pause time).
- **The prototype with 1,500 scripts is faster than main with 900 scripts that fit in the cache** (2.73 M vs
  0.93 M msg/s). Main's per-evaluation registry lookup and binding costs (findings 1–2) remain with 900 scripts.
- **More live memory than main with 900 scripts: 110 vs 76 MB heap, 88.7 vs 65.5 MB metaspace.** All 1,500 script
  classes stay reachable through their expressions, including the 500 the shared cache has evicted, against 900 on
  main. The 5 MB of startup humongous regions (see the table above) is part of both. That the difference is the extra
  600 classes and their expressions is consistent with the numbers (~38 KB of metaspace per class) but was not
  measured with a heap histogram.
- **0.73× the 3-script prototype run** (2.73 M vs 3.74 M msg/s). Throughput climbs from 0.53 M msg/s at 20 s to
  2.7 M at 85 s and then holds at 2.72–2.80 M. This is the same "many classes, each run rarely" JIT behaviour as
  scenario 5c, now with 1,500 script classes of one route. It was not profiled in this run.
- **Interference:** macOS `mediaanalysisd` used ~80% of a core during the last ~20 s. Throughput fell from 2.78 M to
  2.41 M msg/s in the 290–300 s samples, which lowers the 60–300 s average by ~1%.
- The main row predates the harness fix and the classpath change (see the load table above: a few percent for java
  and groovy). At 5,000 msg/s, histogram
  contention cannot explain a 544× gap.

## 10. Groovy 6.0.0-RC-1 vs Groovy 5.1.2

Same camel-groovy (main, `4.23.0-SNAPSHOT`), same Camel and JDK 21, only the Groovy runtime changes
(`-Dgroovy-bench-version`). The run's surefire classpath confirms `groovy-6.0.0-RC-1.jar` and `groovy-json`
6.0.0-RC-1. Throughput only: the phase ran without `-prof gc`, so allocation was not measured. Groovy 5.1.2 ran twice,
back to back (18:57–19:10 and 19:10–19:23), and Groovy 6.0.0-RC-1 once (19:23–19:37). Results are in
`GroovyExpressionTest-jdk21-groovy-5.1.2.jmh.json` (run 1), `GroovyCollectionTest-jdk21-groovy-5.1.2.jmh.json`
(run 2) and `GroovyExpressionTest-jdk21-groovy-6.0.0-RC-1.jmh.json`. A misconfigured include regex ran all 17
benchmarks in each class run, so each of those files holds all 17. The three duplicate class runs that remained were
skipped, and the script is fixed.

| benchmark | items | Groovy 5.1.2 run 1 ops/s | Groovy 5.1.2 run 2 ops/s | Groovy 6.0.0-RC-1 ops/s | 6 vs mean of 5.1.2 | 5.1.2 run-to-run spread |
|---|---:|---:|---:|---:|---:|---:|
| `groovyDynamic` (groovy language) | 10 | 1,709,845 ± 16,361 | 1,724,095 ± 5,839 | 2,607,513 ± 32,713 | **1.52×** | 0.8% |
| `groovyCompileStatic` (groovy language + `GroovyShellFactory`) | 10 | 1,501,852 ± 3,346 | 1,509,817 ± 3,715 | 2,199,350 ± 28,194 | **1.46×** | 0.5% |
| `precompiledDynamicBean` (`bean` language) | 10 | 2,061,906 ± 13,906 | 2,146,789 ± 11,929 | 3,558,575 ± 35,346 | **1.69×** | 4.0% |
| `precompiledStaticBean` (`bean` language) | 10 | 2,015,993 ± 12,948 | 2,050,195 ± 19,963 | 3,529,650 ± 45,406 | **1.74×** | 1.7% |
| `precompiledDynamicDirect` (no Camel) | 10 | 1,939,381 ± 786,670 | 1,486,827 ± 31,726 | 8,842,756 ± 48,111 | *5.16×* | 26.4% |
| `precompiledStaticDirect` (no Camel) | 10 | 2,712,259 ± 403,564 | 2,301,254 ± 519,044 | 8,382,330 ± 44,493 | *3.34×* | 16.4% |
| `groovyDynamic` | 1000 | 16,074 ± 269 | 16,776 ± 298 | 108,233 ± 652 | **6.59×** | 4.3% |
| `groovyCompileStatic` | 1000 | 19,940 ± 4,936 | 17,640 ± 300 | 97,933 ± 681 | **5.21×** | 12.2% |
| `precompiledDynamicBean` | 1000 | 16,521 ± 272 | 16,397 ± 402 | 109,344 ± 656 | **6.64×** | 0.8% |
| `precompiledStaticBean` | 1000 | 16,995 ± 208 | 17,543 ± 547 | 99,594 ± 1,055 | **5.77×** | 3.2% |
| `precompiledDynamicDirect` | 1000 | 16,013 ± 337 | 16,055 ± 392 | 109,545 ± 255 | *6.83×* | 0.3% |
| `precompiledStaticDirect` | 1000 | 16,976 ± 238 | 17,137 ± 313 | 99,244 ± 250 | *5.82×* | 0.9% |
| `concatGroovy` | | 3,031,087 ± 25,765 | 3,021,363 ± 18,287 | 3,041,222 ± 11,608 | 1.00× | 0.3% |
| `arithmeticGroovy` | | 3,675,432 ± 34,177 | 3,653,309 ± 25,907 | 3,697,779 ± 85,180 | 1.01× | 0.6% |
| `predicateGroovy` | | 3,637,333 ± 13,746 | 3,619,045 ± 4,286 | 3,590,388 ± 69,481 | 0.99× | 0.5% |
| `groovyRoute1Thread` | | 657,554 ± 11,577 | 657,497 ± 1,516 | 661,397 ± 7,138 | 1.01× | 0.0% |
| `groovyRoute8Threads` | | 1,423,914 ± 5,619 | 1,393,676 ± 8,445 | 1,410,191 ± 55,800 | 1.00× | 2.1% |

- **Groovy 6 makes the closure over a collection 5.2–6.8× faster at 1,000 items.** This holds for every Groovy variant
  that runs through Camel: the `groovy` language, dynamic or `@CompileStatic`, and pre-compiled classes through the
  `bean` language. The gains are far outside the 0.3–12% run-to-run spread of 5.1.2. With Groovy 5.1.2 the
  `any { it.value > 100 }` evaluation was ~11× slower than Java streams (scenario 3). With 6.0.0-RC-1 the `groovy`
  language reaches 108,233 ops/s, against 184,777 ± 54,517 for Java streams in the 16:40 run: ~0.6× Java at 1,000
  items. Why the loop got faster (fewer per-element allocations, closure call path, indy changes) was not measured
  here. This run has no allocation or cpu profile, so finding 6 stays as measured on 5.1.2.
- **At 10 items it is 1.46–1.74× faster through Camel.** The fixed per-evaluation overhead of camel-groovy
  (findings 1–2, unchanged here) limits the gain. The pre-compiled classes called directly (no Camel) gain 3.3–5.2×,
  and with Groovy 6 their forks agree (±0.5%). They are listed for completeness and are not part of the end-to-end
  comparison (see scenario 3 on their fork-dependent levels with 5.1.2).
- **Expressions and routes do not change (0.99–1.01×).** For `body + '-' + header.foo`, `body * 2 + 1` and
  `headers.amount > 100`, the Groovy runtime is not the bottleneck. The time goes into camel-groovy's per-evaluation
  work (registry lookup, binding, script instantiation), which the prototype of section 9 removes. The Groovy 6
  upgrade and the prototype are therefore independent: one speeds up script bodies that iterate, the other speeds up
  every evaluation.
- **Interference:** macOS `signpost_reporter` used ~80% of a core from ~19:28, which is ~35% into the 6.0.0-RC-1 run,
  through its end. It overlapped `precompiledDynamicDirect` onward: `precompiledStaticBean`, `precompiledStaticDirect`,
  the three expressions and both routes (the 8-thread route has a ±4% error). The first three collection benchmarks
  ran before it. Interference lowers throughput, so it cannot explain the collection gains. A small Groovy 6 effect on
  expressions and routes could be hidden by it, so their 1.00× is "no large change", not "no change".
- **Status:** 6.0.0-RC-1 is a release candidate. The earlier camel-groovy review noted that Spock, which Camel's build
  uses, blocks moving to Groovy 6; that was not re-checked for this report. These numbers argue for tracking the
  Groovy 6 upgrade, not for switching now.

## 11. JDK 17 and JDK 25 vs JDK 21

Same code: camel-groovy main, Groovy 5.1.2. `GroovyExpressionTest` and `GroovyRouteTest` ran in throughput mode with
`-prof gc`, 2 forks × 5 × 2 s, on Corretto 17.0.18 and Temurin 25.0.2 (JDK 25 with `--enable-native-access=ALL-UNNAMED`
for GraalJS/GraalPy). They are compared with the Temurin 21.0.10 results of section 4
(`python3 compare_jmh.py raw/GroovyRouteTest-jdk21.jmh.json raw/GroovyRouteTest-jdk25.jmh.json`). GraalJS and GraalPy
ran `Interpreted` on all three JDKs. Timeline: JDK 17 ran 19:48–20:20 and JDK 25 20:20–20:53. Background load was under half a core (window server,
terminal and wallpaper extension at ~40% of one core combined in a 20:36 sample).

**Full routes, end to end:**

| route | JDK 17 msg/s | JDK 21 msg/s | JDK 25 msg/s | 17 vs 21 | 25 vs 21 | bytes/msg 17 / 21 / 25 |
|---|---:|---:|---:|---:|---:|---:|
| groovy, 1 thread | 624,508 ± 7,207 | 652,420 ± 3,466 | 681,764 ± 7,377 | 0.96× | 1.04× | 5,056 / 4,664 / 4,652 |
| **groovy, 8 threads** | 1,343,300 ± 34,898 | 1,374,665 ± 14,398 | **1,815,325 ± 45,320** | 0.98× | **1.32×** | 5,024 / 4,704 / 4,640 |
| Java, 1 thread | 1,361,244 ± 12,169 | 1,352,257 ± 9,711 | 1,376,106 ± 14,174 | 1.01× | 1.02× | 1,560 / 1,560 / 1,560 |
| Java, 8 threads | 6,746,035 ± 187,928 | 6,321,578 ± 668,119 | 6,602,609 ± 72,276 | 1.07× | 1.04× | 1,536 / 1,536 / 1,548 |
| jactl, 1 thread | 1,321,886 ± 14,115 | 1,338,124 ± 9,470 | 1,349,784 ± 4,113 | 0.99× | 1.01× | 1,696 / 1,696 / 1,696 |
| jactl, 8 threads | 6,409,544 ± 187,695 | 6,256,786 ± 397,590 | 5,853,333 ± 943,582 | 1.02× | 0.94× | 1,672 / 1,672 / 1,696 |
| java (jOOR), 1 thread | 1,336,766 ± 17,872 | 1,378,663 ± 17,810 | 1,379,933 ± 7,573 | 0.97× | 1.00× | 1,592 / 1,560 / 1,560 |
| java (jOOR), 8 threads | 5,665,586 ± 926,428 | 6,567,132 ± 340,895 | 6,604,061 ± 85,763 | 0.86× | 1.01× | 1,536 / 1,536 / 1,536 |
| mvel, 1 thread | 1,271,165 ± 7,831 | 1,246,366 ± 25,547 | 1,276,831 ± 16,534 | 1.02× | 1.02× | 1,784 / 1,784 / 1,784 |
| mvel, 8 threads | 6,003,607 ± 589,882 | 6,202,373 ± 111,185 | 6,067,589 ± 602,781 | 0.97× | 0.98× | 1,760 / 1,772 / 1,784 |
| simple, 1 thread | 1,274,828 ± 9,969 | 1,201,081 ± 35,625 | 1,207,307 ± 30,576 | 1.06× | 1.01× | 1,856 / 1,856 / 1,856 |
| simple, 8 threads | 5,805,946 ± 806,989 | 5,626,434 ± 439,314 | 5,848,055 ± 352,901 | 1.03× | 1.04× | 1,832 / 1,844 / 1,844 |
| js, 1 thread | 1,520 ± 29 | 1,567 ± 54 | 1,672 ± 33 | 0.97× | 1.07× | 1.84 / 1.73 / 1.72 MB |
| js, 8 threads | 5,912 ± 21 | 6,135 ± 358 | 6,182 ± 466 | 0.96× | 1.01× | 1.84 / 1.73 / 1.73 MB |
| python3, 1 thread | 60.0 ± 2.4 | 59.2 ± 2.4 | 61.3 ± 3.1 | 1.01× | 1.04× | 11.3 / 11.0 / 11.0 MB |
| python3, 8 threads | 372 ± 19 | 400 ± 20 | 415 ± 13 | 0.93× | 1.04× | 11.3 / 11.0 / 11.0 MB |

- **JDK 25 makes the 8-thread groovy route 1.32× faster (1.37 M → 1.82 M msg/s), but the 1-thread groovy route only
  1.04×.** Both JDK 25 forks agree (1.79 and 1.84 M). All six JDK 21 forks from three separate runs (the section 4
  baseline and the two Groovy 5.1.2 repeats of section 10) lie between 1.35 and 1.43 M. The gain appears only under
  concurrency, which points at the contended `DefaultRegistry` monitor of finding 1 getting cheaper on JDK 25. HotSpot's
  monitor implementation has changed since JDK 21, but no lock profile was taken on JDK 25, so which change helps is not
  verified. It narrows the gap without closing it: on JDK 25 the 8-thread groovy route is still 0.27× the Java route
  (1.82 M vs 6.60 M msg/s). The camel-groovy prototype on JDK 21 reaches 5.27 M, ~2.9× JDK 25 without the fix.
- **JDK 17 is slightly slower for groovy (0.96–0.98×) and allocates 320–390 B more per message.** The groovy
  expressions are 0.87–0.90× with 150–200 B more per evaluation. Every other route on JDK 17 is within 0.93–1.07×. The
  one outlier, java (jOOR) with 8 threads at 0.86×, has a ±16% error bar.
- **Every other route is within 0.94–1.07× on JDK 25.** The lowest, jactl with 8 threads at 0.94× (±16%) and mvel with
  8 threads at 0.98× (±10%), have wide error bars.
- **Single-expression benchmarks move more than routes, in both directions, because they time a few nanoseconds of
  work.** JDK 17 runs `predicateJava` at 0.42× (280 M → 116 M ops/s) and `predicateJavaLanguage` at 0.73×. JDK 25 runs
  `concatJavaExpression` at 0.84×, `predicateJavaLanguage` at 0.76× and `predicateMvel` at 1.20×. The forks agree, so
  these are real JIT differences, but none of them shows up in a route, where Camel's own work is ~740 ns per message.
  `predicateJactl` on JDK 17 (0.86×) is fork-dependent: 73.6 M and 53.6 M ops/s in its two forks. The groovy
  expressions are 1.01–1.08× on JDK 25. js and python3 are 7–17% faster on JDK 25, still `Interpreted`.
- **Takeaway:** the conclusions of sections 4–10 hold on JDK 17 and JDK 25. JDK 25 softens finding 1 under
  concurrency, but on the 8-thread route the prototype's improvement is still ~2.9× larger.

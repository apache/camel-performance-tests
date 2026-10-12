# camel-groovy performance benchmarks

## Camel 4.23 results

These benchmarks drove the scripting language improvements in Camel 4.23 (CAMEL-24682, CAMEL-24683, CAMEL-24684,
CAMEL-24685, CAMEL-24687, CAMEL-24688, CAMEL-24689, CAMEL-24690). Before is 4.23.0-SNAPSHOT before the fixes (the
same code as Camel 4.22, except QuickJS which is new in 4.23); JDK 21, Apple M1 Pro, 10 cores:

| Benchmark (8 threads unless noted)            | Before                   | Camel 4.23               | Speed-up | Source |
|-----------------------------------------------|--------------------------|--------------------------|---------:|--------|
| Groovy predicate, 1 thread                    | 3.6 M ops/s              | 25.3 M ops/s             |     7.0x | `allfixes-compare.md` |
| Groovy expression (string concat), 1 thread   | 3.0 M ops/s              | 14.8 M ops/s             |     4.9x | `allfixes-compare.md` |
| Groovy route (filter + setBody)               | 1.37 M msg/s             | 5.87 M msg/s             |     4.3x | `raw/GroovyRouteTest-jdk21{,-allfixes}.jmh.json` |
| Groovy 5-minute load test                     | 1.08 M msg/s, p99 102 us | 3.80 M msg/s, p99 3 us   |     3.5x | `raw/load/GroovyLoadTest-groovy-{harness2,allfixes}.txt` |
| Groovy load test, 1,500 different scripts     | 5,000 msg/s              | 2.92 M msg/s             |     580x | `raw/load/GroovyLoadTest-groovyManyScripts{,-allfixes}.txt` |
| `groovyXml` unmarshal, 1 KB                   | 33.2 us                  | 10.8 us                  |     3.1x | `allfixes-compare.md` |
| JavaScript (GraalJS) 5-minute load test       | 4,700 msg/s              | 15,000 msg/s             |     3.2x | `raw/load/GroovyLoadTest-js{,-allfixes}.txt` |
| QuickJS route                                 | 5,350 msg/s              | 10,400 msg/s             |     1.9x | `raw/GroovyRouteTest-jdk21-{quickjs-baseline,allfixes}.jmh.json` |
| QuickJS 5-minute load test                    | out of memory after 22 s | 8,860 msg/s, stable heap |       -- | `raw/load/GroovyLoadTest-quickjs-allfixes-v2.txt` |

The `groovyJson` pretty print change that was merged (CAMEL-24683) measured 60.8 us -> 14.9 us at 1 KB and
55.6 ms -> 6.1 ms at 1 MB; `allfixes-compare.md` holds an earlier, slower attempt. `REPORT.md` is the review of
camel-groovy on 4.23.0-SNAPSHOT before the fixes, the `-allfixes` files are the runs with all fixes applied.

Benchmarks and load tests comparing Java, `simple` and `groovy` in Camel routes, plus the `groovyJson` / `groovyXml`
data formats. Sources are in `src/test/java/org/apache/camel/itest/jmh/groovy`, the pre-compiled Groovy classes in
`src/test/resources/camel-groovy`.

## Prerequisites

This module builds against the Camel version in the root `pom.xml` (`camel.version`, 4.23.0-SNAPSHOT on this branch).
A SNAPSHOT needs a local build of apache/camel:

```bash
cd /path/to/camel
mvn install -Dquickly -pl :camel-groovy,:camel-jackson,:camel-jacksonxml,:camel-netty,:camel-joor,:camel-disruptor,:camel-dependencies,:camel-main,:camel-bom -am
```

Check what resolves with `mvn dependency:tree -Dincludes=org.apache.camel` (from `tests/camel-jmh`).

Flamegraphs need [async-profiler](https://github.com/async-profiler/async-profiler/releases) (4.5 was used).

## Benchmarks

The expression, collection, route, first-evaluation and load scenarios also compare the other general purpose
scripting languages of Camel with the same logic: `jactl`, `java` (jOOR, named `javaLanguage` in the benchmarks),
`mvel`, `js` (GraalJS), `python3` (GraalPy) and `quickjs` (QuickJS4J). `ognl` is deprecated and `python` (Jython 2.7)
is not included. jactl and python3 cannot call methods on Java objects by default (sandbox), so the scenarios with a
POJO body use `JactlLanguage.createWithHostAccess()` / `Python3Language.createWithHostAccess()`. quickjs binds JSON
snapshots (`body`, `headers`, `properties`, `exchangeId`) rather than live Java objects: a POJO body is serialized with
Jackson per evaluation (`getLineItems()` becomes `body.lineItems`), and the result comes back through Jackson, so it
needs no host access but pays for the serialization.

| Class | Scenario | Default settings |
|---|---|---|
| `GroovyExpressionTest` | 1: body/header concat and arithmetic; 2: header predicate. Java `Processor`, Java `Expression`, `simple`, `groovy`, `jactl`, `java`, `mvel`, `js`, `python3`, `quickjs` | thrpt (avgt would only be 1/thrpt), 2 forks, 5x2s warmup, 5x2s measurement; `-Djmh.modes=sample` for route p99 |
| `GroovyCollectionTest` | 3: `any line item > 100` over 10/1000 items. Java streams, groovy dynamic, groovy `@CompileStatic` (via `GroovyShellFactory`), pre-compiled Groovy classes called directly and via the `bean` language, `jactl`, `java`, `mvel`, `js`, `python3`, `quickjs` | same |
| `GroovyRouteTest` | 4: `direct -> filter -> setBody -> counter` via `ProducerTemplate`, 1 and 8 threads, Java and every language | same |
| `GroovyFirstEvaluationTest` | 5a: first evaluation on a new CamelContext (JVM-cold first iteration per fork), every language | SingleShotTime, 10 forks, 0 warmup, 20 iterations |
| `GroovyScriptCacheTest` | 5b/5c: compiling N distinct scripts; round-robin over 100/1000/1001/2000 scripts (cache size is 1000) | avgt (SingleShotTime for compile) |
| `GroovyScriptCacheChurnTest` | 5d: harness (not JMH) counting recompilations, class loading and Metaspace: cache eviction, hot script eviction, concurrent misses, soft reference clearing | - |
| `GroovyOverheadTest` | 6: registry and binding overhead, step by step, with 0/500 registry beans and with/without a `GroovyShellFactory`; benchmark-local prototypes (`OptimizedGroovyExpression`) | thrpt+avgt |
| `GroovyJsonDataFormatTest` | 7: `groovyJson` vs Jackson marshal/unmarshal, 1 KB / 1 MB | avgt |
| `GroovyXmlDataFormatTest` | 7: `groovyXml` unmarshal vs DOM / StAX / jacksonXml; Map to XML marshal | avgt |
| `GroovyLoadTest` | long running high load (heap behaviour): 8 producer threads for 5 minutes (the java, groovy, groovyPrototype, groovyManyScripts and fixed-rate runs used 10 minutes; their 60–300 s averages match 60–600 s within 1%), samples throughput, latency, allocation, old gen after GC, GC pauses, Metaspace every 5 s | - |

Every benchmark checks in `@Setup` that all variants return the same result (`GroovyBenchmarkSupport.check`), except
`marshalGroovyCompact`: before CAMEL-24669 (apache/camel#26260) groovyJson `prettyPrint=false` wrote the JSON document
as a quoted string, and the setup prints a `SETUP ... NOT equal work` line when the Camel build under test still has
that bug. The XML marshal benchmarks are not equal-work checked either: groovyXml writes the `_id` / `_sku` keys as
attributes and jacksonXml as elements (41 vs 54 elements for the 1 KB payload, printed by the setup), and
`unmarshalJacksonXml` is only checked to return a `Map`.

## Running

All phases, sequentially (about 5 hours):

```bash
cd tests/camel-jmh
ASYNC_PROFILER=/path/to/async-profiler-4.5-macos/lib/libasyncProfiler.dylib \
CAMEL_DIR=/path/to/camel-with-prototype \
./groovy-results/run-groovy-benchmarks.sh all
```

Or one phase at a time: `load`, `languages-load`, `jdk21`, `flamegraphs`, `churn`, `prototype`, `groovy6`, `jdk17`,
`jdk25`, `quickjs-baseline` (only the quickjs benchmarks and load, suffix `-jdk21-quickjs-baseline` / `-baseline`),
`allfixes` (the `jdk21` phase again plus the load runs of every language, suffix `-jdk21-allfixes` / `-allfixes`, for a
Camel build with all the fixes applied).

All languages share one test classpath. JMH forks a new JVM per benchmark and only the benchmarked language runs in the
measured loop, so steady-state numbers are not affected by the other jars. CamelContext startup (type converter
discovery over all camel-* jars) and the absolute Metaspace of the load test include the other languages' jars; for
per-language startup or Metaspace figures, a module per language would be cleaner.

A single benchmark class:

```bash
mvn test -P jmh -Dtest=GroovyRouteTest -Djmh.prof=gc
mvn test -P jmh -Dtest=GroovyRouteTest -Djmh.modes=sample                      # p99
mvn test -P jmh -Dtest=GroovyExpressionTest -Djmh.forks=1 -Djmh.i=3 -Djmh.modes=avgt \
  '-Djmh.include=org.apache.camel.itest.jmh.groovy.GroovyExpressionTest.concatGroovy$' \
  '-Djmh.prof=async:libPath=/path/libasyncProfiler.dylib;output=flamegraph;event=cpu;dir=flame'
mvn test -P jmh -Dtest=GroovyScriptCacheChurnTest -DargLine=-XX:SoftRefLRUPolicyMSPerMB=0
mvn test -P jmh -Dtest=GroovyLoadTest -Dload.variant=groovy -Dload.duration=600 \
  "-DargLine=-Xms1g -Xmx1g -Xlog:gc*:file=groovy-gc.log:time,uptime,level,tags -XX:StartFlightRecording=filename=groovy.jfr,settings=profile"
```

Options (system properties, see `GroovyBenchmarkSupport`):

| Property | Meaning |
|---|---|
| `jmh.include` | regexp of benchmarks (default: the whole class) |
| `jmh.forks`, `jmh.wi`, `jmh.w`, `jmh.i`, `jmh.r` | forks, warmup iterations / seconds, measurement iterations / seconds |
| `jmh.modes` | comma separated: `thrpt`, `avgt`, `sample`, `ss` |
| `jmh.prof` | profilers separated by `\|`, e.g. `gc\|cl` |
| `jmh.jvmArgs` | JVM args of the forked JVMs (default `-Xms2g -Xmx2g`) |
| `jmh.resultDir`, `jmh.suffix` | output directory and file name suffix of the JSON result |
| `groovy-bench-version` | Groovy runtime version (default 5.1.2, e.g. `6.0.0-RC-1`) |
| `camel-groovy-bench-version` | camel-groovy version, e.g. a prototype installed with `install-prototype.sh` |
| `load.variant`, `load.threads`, `load.duration`, `load.interval`, `load.warmup`, `load.rate`, `load.scripts` | `GroovyLoadTest` settings; variants: `java`, `groovy`, `groovyPrototype`, `groovyManyScripts`, `jactl`, `javaLanguage`, `mvel`, `js`, `python3`, `quickjs` |

## Results layout

To keep the repository small, the run logs, GC logs, flamegraphs (HTML and collapsed stacks) and JFR recordings are not
committed; re-run the phases to regenerate them. `REPORT.md` still quotes figures taken from them.

```
groovy-results/
  REPORT.md                 findings and tables
  raw/*.jmh.json            JMH results (<Class>-<jdk>[-variant].jmh.json)
  raw/load/                 GroovyLoadTest CSV + summary (*.txt)
  raw/GroovyScriptCacheChurnTest-*.txt
  charts/load-unbounded/    heap/GC/throughput over time, all unbounded load variants, log scale
  charts/load-java-tier/    same metrics, linear scale: java, jactl, mvel, java (jOOR), groovy, groovyPrototype
  charts/load-100k/         java vs groovy at a fixed 100,000 msg/s
```

Tables and charts are generated with (run from `tests/camel-jmh/groovy-results`):

```bash
python3 jmh_tables.py raw/GroovyRouteTest-jdk21.jmh.json
python3 load_tables.py --warmup 60 --until 300 raw/load/GroovyLoadTest-*.csv
# GC pauses (young, mixed, remark, cleanup, full) and heap after young GC: use the GC logs, not the CSV GC columns
python3 gc_log_tables.py --warmup 60 --until 300 raw/load/*-gc.log
python3 load_charts.py --log charts/load-unbounded raw/load/GroovyLoadTest-{java,jactl,mvel,javaLanguage,groovyPrototype,groovy,groovyManyScripts,js,python3}.csv
python3 load_charts.py charts/load-java-tier raw/load/GroovyLoadTest-{java,jactl,mvel,javaLanguage,groovyPrototype,groovy}.csv
python3 load_charts.py charts/load-100k raw/load/GroovyLoadTest-{java,groovy}-rate100000.csv
# JFR recordings are not committed (raw/.gitignore, 1.9 GB); re-run the load phases to regenerate them
./jfr_views.sh raw/load/*.jfr
# before/after of the camel-groovy prototype (rows matched on benchmark, mode and @Param values)
python3 compare_jmh.py raw/GroovyRouteTest-jdk21.jmh.json raw/GroovyRouteTest-jdk21-prototype.jmh.json '^groovyRoute'
# top self and inclusive frames of an async-profiler collapsed profile
python3 flame_top.py raw/flamegraphs-collapsed/cpu/<benchmark>/collapsed-cpu.csv 15
```

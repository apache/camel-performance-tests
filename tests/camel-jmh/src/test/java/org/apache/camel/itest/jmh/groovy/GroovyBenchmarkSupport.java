/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.camel.itest.jmh.groovy;

import java.io.File;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.TimeUnit;

import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.options.ChainedOptionsBuilder;
import org.openjdk.jmh.runner.options.OptionsBuilder;
import org.openjdk.jmh.runner.options.TimeValue;

/**
 * Shared JMH options and checks for the Groovy benchmarks.
 * <p>
 * Every option can be overridden with a system property, for example:
 *
 * <pre>
 * mvn test -P jmh -Dtest=GroovyExpressionTest -Djmh.prof=gc -Djmh.suffix=-jdk21 -Djmh.resultDir=results
 * </pre>
 *
 * <ul>
 * <li>jmh.include - regexp of benchmarks to run (default: all benchmarks of the class)</li>
 * <li>jmh.forks, jmh.wi, jmh.w, jmh.i, jmh.r - forks, warmup iterations/seconds, measurement iterations/seconds</li>
 * <li>jmh.modes - comma separated JMH modes (thrpt, avgt, sample, ss)</li>
 * <li>jmh.prof - profilers separated by '|', e.g. {@code gc|async:libPath=...;output=flamegraph;event=cpu}</li>
 * <li>jmh.jvmArgs - JVM arguments of the forked benchmark JVMs (default: -Xms2g -Xmx2g)</li>
 * <li>jmh.threads, jmh.tu - threads and time unit overrides</li>
 * <li>jmh.resultDir, jmh.suffix - where the JSON result is written and a suffix for its file name</li>
 * </ul>
 */
public final class GroovyBenchmarkSupport {

    public static final String RESULT = "benchmarkResult";

    private GroovyBenchmarkSupport() {
    }

    public static ChainedOptionsBuilder options(Class<?> benchmark, String modes) {
        return options(benchmark, modes, 2, 5, 2, 5, 2);
    }

    public static ChainedOptionsBuilder options(
            Class<?> benchmark, String modes, int forks, int warmupIterations, int warmupSeconds,
            int measurementIterations, int measurementSeconds) {
        String dir = System.getProperty("jmh.resultDir", ".");
        new File(dir).mkdirs();
        String suffix = System.getProperty("jmh.suffix", "");

        ChainedOptionsBuilder builder = new OptionsBuilder()
                .include(System.getProperty("jmh.include", benchmark.getName() + ".*"))
                .forks(Integer.getInteger("jmh.forks", forks))
                .warmupIterations(Integer.getInteger("jmh.wi", warmupIterations))
                .warmupTime(TimeValue.seconds(Integer.getInteger("jmh.w", warmupSeconds)))
                .measurementIterations(Integer.getInteger("jmh.i", measurementIterations))
                .measurementTime(TimeValue.seconds(Integer.getInteger("jmh.r", measurementSeconds)))
                .shouldFailOnError(true)
                .resultFormat(ResultFormatType.JSON)
                .result(dir + "/" + benchmark.getSimpleName() + suffix + ".jmh.json");

        String jvmArgs = System.getProperty("jmh.jvmArgs", "-Xms2g -Xmx2g");
        if (!jvmArgs.isBlank()) {
            builder.jvmArgs(jvmArgs.trim().split("\\s+"));
        }
        for (String mode : System.getProperty("jmh.modes", modes).split(",")) {
            builder.mode(Mode.deepValueOf(mode.trim()));
        }
        String timeUnit = System.getProperty("jmh.tu");
        if (timeUnit != null) {
            builder.timeUnit(TimeUnit.valueOf(timeUnit));
        }
        String threads = System.getProperty("jmh.threads");
        if (threads != null) {
            builder.threads(Integer.parseInt(threads));
        }
        String profilers = System.getProperty("jmh.prof");
        if (profilers != null && !profilers.isBlank()) {
            for (String profiler : profilers.split("\\|")) {
                int pos = profiler.indexOf(':');
                if (pos > 0) {
                    builder.addProfiler(profiler.substring(0, pos), profiler.substring(pos + 1));
                } else {
                    builder.addProfiler(profiler);
                }
            }
        }
        return builder;
    }

    /**
     * Fails the trial when two variants do not produce the same result, so every benchmark compares equal work.
     */
    public static void check(String variant, Object expected, Object actual) {
        if (!Objects.equals(expected, actual)) {
            throw new IllegalStateException(
                    "Variant " + variant + " returned [" + actual + "] but expected [" + expected + "]");
        }
    }

    /**
     * Walks a parsed JSON/XML tree and returns a checksum (number of leaves + length of textual leaves), which also
     * forces lazy parsers to materialize every value.
     */
    public static long walk(Object value) {
        if (value instanceof Map<?, ?> map) {
            long n = 0;
            for (Map.Entry<?, ?> e : map.entrySet()) {
                n += e.getKey().toString().length();
                n += walk(e.getValue());
            }
            return n;
        } else if (value instanceof Iterable<?> it) {
            long n = 0;
            for (Object o : it) {
                n += walk(o);
            }
            return n;
        } else if (value instanceof CharSequence cs) {
            return 1 + cs.length();
        } else if (value != null) {
            return 1 + (value.toString().isEmpty() ? 0 : 1);
        }
        return 1;
    }
}

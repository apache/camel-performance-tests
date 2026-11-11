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
package org.apache.camel.itest.jmh;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;

import org.apache.camel.CamelContext;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.builder.RouteBuilder;
import org.apache.camel.impl.DefaultCamelContext;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.annotations.Threads;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;
import org.openjdk.jmh.runner.options.TimeValue;

/**
 * The cost per message of the exchange sanitizer (camel-sanitizer), and of the table of pending calls of its rule R1
 * "still pending" (CAMEL-26751, apache/camel#29528).
 * <p/>
 * It needs camel-sanitizer on the classpath, so it runs with the profile {@code sanitizer} and a Camel version that has
 * the {@code pendingTimeout} option:
 *
 * <pre>
 * mvn -Pjmh,sanitizer -Dcamel.version=4.24.0-SNAPSHOT -Dtest=SanitizerPendingTest -DargLine="-Xms1g -Xmx1g" clean test
 * </pre>
 *
 * {@code mode}: {@code off} = camel-sanitizer on the classpath with {@code camel.sanitizer.enabled=false}; {@code t0} =
 * on with {@code pendingTimeout=0} (the records of R1, no table); {@code t60} = on with {@code pendingTimeout=60s} (the
 * records, the table of pending calls, the exchange-done notifier and the checker thread). {@code stackDepth} is the
 * sanitizer option (0 = no stacks; 32 = the default). The context, and so the table, is shared by all the benchmark
 * threads ({@code send_1} and {@code send_4}).
 * <p/>
 * The routes:
 * <ul>
 * <li>{@code steps}: 6 step calls per message (setHeader, setBody, process, filter, process in the filter, to mock).</li>
 * <li>{@code split}: a split of a 4-element list (each part: setHeader, process), then an InOnly send to seda whose
 * consumer sends to mock.</li>
 * <li>{@code psplit4}, {@code psplit8}: a parallel split of a 16-element list (each part: setHeader, process) on a pool
 * of 4 or 8 threads. The parts of one exchange are in the stripe of the table of their exchange, so the pool threads
 * take the same stripe lock; run it with {@code send_1} (one producer thread).</li>
 * </ul>
 */
public class SanitizerPendingTest {

    @Test
    public void launchBenchmark() throws Exception {
        // without the profile sanitizer (or with a Camel version without camel-sanitizer) it is skipped
        Assumptions.assumeTrue(sanitizerOnClasspath(), "camel-sanitizer is not on the classpath (profile sanitizer)");
        Options opt = new OptionsBuilder()
                // Specify which benchmarks to run.
                // You can be more specific if you'd like to run only one benchmark per test.
                .include(this.getClass().getName() + ".*")
                // Set the following options as needed
                .warmupIterations(3)
                .warmupTime(TimeValue.seconds(2))
                .measurementIterations(5)
                .measurementTime(TimeValue.seconds(2))
                .forks(2)
                .shouldFailOnError(true)
                .shouldDoGC(true)
                .resultFormat(ResultFormatType.JSON)
                .result(this.getClass().getSimpleName() + ".jmh.json")
                .build();

        new Runner(opt).run();
    }

    private static boolean sanitizerOnClasspath() {
        try {
            Class.forName("org.apache.camel.sanitizer.Sanitizer");
            return true;
        } catch (ClassNotFoundException e) {
            return false;
        }
    }

    // The JMH samples are the best documentation for how to use it
    // http://hg.openjdk.java.net/code-tools/jmh/file/tip/jmh-samples/src/main/java/org/openjdk/jmh/samples/
    @State(Scope.Benchmark)
    public static class BenchmarkState {

        @Param({ "steps", "split", "psplit4", "psplit8" })
        String route;

        @Param({ "off", "t0", "t60" })
        String mode;

        @Param({ "0", "32" })
        String stackDepth;

        CamelContext camel;
        ProducerTemplate producer;
        ExecutorService pool;
        String uri;
        Object body;

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            camel = new DefaultCamelContext();
            camel.getPropertiesComponent().addInitialProperty("camel.sanitizer.enabled", "off".equals(mode) ? "false" : "true");
            camel.getPropertiesComponent().addInitialProperty("camel.sanitizer.pendingTimeout", "t60".equals(mode) ? "60s" : "0");
            camel.getPropertiesComponent().addInitialProperty("camel.sanitizer.stackDepth", stackDepth);
            int threads = route.startsWith("psplit") ? Integer.parseInt(route.substring("psplit".length())) : 1;
            pool = camel.getExecutorServiceManager().newFixedThreadPool(this, "psplit", threads);
            camel.addRoutes(new RouteBuilder() {
                @Override
                public void configure() {
                    from("direct:steps").routeId("steps")
                            .setHeader("step", constant(1))
                            .setBody(simple("${body}"))
                            .process(e -> e.getMessage().setHeader("seen", Boolean.TRUE))
                            .filter(header("step").isEqualTo(1))
                                .process(e -> e.getMessage().setHeader("filtered", Boolean.TRUE))
                            .end()
                            .to("mock:result?retainFirst=0");

                    from("direct:split").routeId("split")
                            .split(body())
                                .setHeader("part", constant(1))
                                .process(e -> e.getMessage().setHeader("seen", Boolean.TRUE))
                            .end()
                            .to("seda:copy?waitForTaskToComplete=Never&blockWhenFull=true");

                    from("seda:copy?concurrentConsumers=2").routeId("copy")
                            .to("mock:copy?retainFirst=0");

                    from("direct:psplit").routeId("psplit")
                            .split(body()).parallelProcessing().executorService(pool)
                                .setHeader("part", constant(1))
                                .process(e -> e.getMessage().setHeader("seen", Boolean.TRUE))
                            .end();
                }
            });
            camel.start();
            if (!"off".equals(mode) && !sanitizerInstalled(camel)) {
                throw new IllegalStateException(
                        "camel-sanitizer is not installed: run with -Psanitizer and a Camel version that has it");
            }
            producer = camel.createProducerTemplate();
            if (route.startsWith("psplit")) {
                uri = "direct:psplit";
                List<String> parts = new ArrayList<>();
                for (int i = 0; i < 16; i++) {
                    parts.add("part" + i);
                }
                body = parts;
            } else {
                uri = "direct:" + route;
                body = "split".equals(route) ? List.of("a", "b", "c", "d") : "Hello World";
            }
        }

        private static boolean sanitizerInstalled(CamelContext camel) {
            try {
                Class<?> type = Class.forName("org.apache.camel.sanitizer.Sanitizer");
                return camel.getCamelContextExtension().getContextPlugin(type) != null;
            } catch (ClassNotFoundException e) {
                return false;
            }
        }

        @TearDown(Level.Trial)
        public void close() {
            try {
                producer.stop();
                camel.stop();
                camel.getExecutorServiceManager().shutdown(pool);
            } catch (Exception e) {
                // ignore
            }
        }
    }

    @OutputTimeUnit(TimeUnit.NANOSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    @Threads(1)
    public void send_1(BenchmarkState state, Blackhole bh) {
        bh.consume(state.producer.requestBody(state.uri, state.body));
    }

    @OutputTimeUnit(TimeUnit.NANOSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    @Threads(4)
    public void send_4(BenchmarkState state, Blackhole bh) {
        bh.consume(state.producer.requestBody(state.uri, state.body));
    }
}

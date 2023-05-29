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

package org.apache.camel.itest.jmh.eip;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import org.apache.camel.CamelContext;
import org.apache.camel.Endpoint;
import org.apache.camel.Exchange;
import org.apache.camel.Processor;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.builder.RouteBuilder;
import org.apache.camel.impl.DefaultCamelContext;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.AuxCounters;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Threads;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;

/**
 * This tests a content-based-router when using a text body for the routing decision. This is suitable for most cases when
 * a large machine with too many cores is not available (as it limits to a maximum of 4 consumers + 4 producers).
 */
public class ContentBasedRouterHeaderTest {
    private static String COUNTER_HEADER = "counter";
    private static String TYPE_A_BODY = "typeA";
    private static String TYPE_B_BODY = "typeB";

    @Test
    public void launchBenchmark() throws Exception {
        Options opt = new OptionsBuilder()
                // Specify which benchmarks to run.
                // You can be more specific if you'd like to run only one benchmark per test.
                .include(this.getClass().getName() + ".*")
                .warmupIterations(5)
                .warmupBatchSize(5000)
                .measurementIterations(10)
                .measurementBatchSize(50000)
                .forks(1)
                .resultFormat(ResultFormatType.JSON)
                .result(this.getClass().getSimpleName() + ".jmh.json")
                .build();

        new Runner(opt).run();
    }

    // The JMH samples are the best documentation for how to use it
    // http://hg.openjdk.java.net/code-tools/jmh/file/tip/jmh-samples/src/main/java/org/openjdk/jmh/samples/
    @State(Scope.Benchmark)
    public static class BenchmarkState {
        @Param({"1", "2", "4"})
        int consumers;

        CamelContext context;
        ProducerTemplate producerTemplate;
        Endpoint endpoint;

        TypeAProcessor typeAProcessor = new TypeAProcessor();
        TypeBProcessor typeBProcessor = new TypeBProcessor();

        Map<String, Object> typeAHeaders = new HashMap<>();
        Map<String, Object> typeBHeaders = new HashMap<>();

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            context = new DefaultCamelContext();

            producerTemplate = context.createProducerTemplate();
            endpoint = context.getEndpoint("disruptor:test");

            context.addRoutes(new RouteBuilder() {
                @Override
                public void configure() {
                    fromF("disruptor:test?concurrentConsumers=%s", consumers)
                            .choice()
                                .when(simple("${header.destination} == 'typeA'"))
                                .process(typeAProcessor)
                            .otherwise()
                                .process(typeBProcessor)
                            .end()
                            .to("log:?level=OFF");
                }
            });

            typeAHeaders.put("destination", "typeA");
            typeBHeaders.put("destination", "typeB");

            context.start();
        }
    }

    @State(Scope.Thread)
    @AuxCounters(AuxCounters.Type.EVENTS)
    public static class EventCounters {
        public int typeA;
        public int typeB;

        public int total() {
            return typeA + typeB;
        }
    }

    public static class TypeAProcessor implements Processor {
        @Override
        public void process(Exchange exchange) throws Exception {
            final EventCounters counter = exchange.getMessage().getHeader(COUNTER_HEADER, EventCounters.class);

            counter.typeA++;
        }
    }

    public static class TypeBProcessor implements Processor {
        @Override
        public void process(Exchange exchange) throws Exception {
            final EventCounters counter = exchange.getMessage().getHeader(COUNTER_HEADER, EventCounters.class);

            counter.typeB++;
        }
    }

    private static void doSend(BenchmarkState state, EventCounters counters) {
        state.typeAHeaders.put(COUNTER_HEADER, counters);
        state.typeBHeaders.put(COUNTER_HEADER, counters);

        state.producerTemplate.sendBodyAndHeaders(state.endpoint, TYPE_A_BODY, state.typeAHeaders);
        state.producerTemplate.sendBodyAndHeaders(state.endpoint, TYPE_B_BODY, state.typeBHeaders);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    public void send_1(BenchmarkState state, EventCounters counters) {
        doSend(state, counters);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    @Threads(2)
    public void send_2(BenchmarkState state, EventCounters counters) {
        doSend(state, counters);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    @Threads(4)
    public void send_4(BenchmarkState state, EventCounters counters) {
        doSend(state, counters);
    }
}

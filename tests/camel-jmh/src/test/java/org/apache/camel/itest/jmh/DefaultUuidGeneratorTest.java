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

import org.apache.camel.support.DefaultUuidGenerator;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Threads;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;

import java.util.concurrent.TimeUnit;

/**
 * Tests the {@link DefaultUuidGenerator}.
 * <p/>
 * Thanks to this SO answer: https://stackoverflow.com/questions/30485856/how-to-run-jmh-from-inside-junit-tests
 */
public class DefaultUuidGeneratorTest {

    @Test
    public void launchBenchmark() throws Exception {
        Options opt = new OptionsBuilder()
                // Specify which benchmarks to run.
                // You can be more specific if you'd like to run only one benchmark per test.
                .include(this.getClass().getName() + ".*")
                // Set the following options as needed
                .mode(Mode.SingleShotTime)
                .timeUnit(TimeUnit.MILLISECONDS)
                .warmupIterations(5)
                .warmupBatchSize(5000)
                .measurementIterations(2)
                .threads(2)
                .forks(1)
                .shouldFailOnError(true)
                .shouldDoGC(true)
                .resultFormat(ResultFormatType.JSON)
                .result(this.getClass().getSimpleName() + ".jmh.json")
                .build();

        new Runner(opt).run();
    }

    // The JMH samples are the best documentation for how to use it
    // http://hg.openjdk.java.net/code-tools/jmh/file/tip/jmh-samples/src/main/java/org/openjdk/jmh/samples/
    @State(Scope.Thread)
    public static class BenchmarkState {
        DefaultUuidGenerator uuid;

        @Setup(Level.Trial)
        public void initialize() {
            uuid = new DefaultUuidGenerator();
        }
    }

    @Benchmark
    @Measurement(batchSize = 1000000)
    public void benchmark(BenchmarkState state, Blackhole bh) {
        String id = state.uuid.generateUuid();
        bh.consume(id);
    }

    @Benchmark
    @Measurement(batchSize = 1000000)
    @Threads(2)
    public void benchmark_2(BenchmarkState state, Blackhole bh) {
        String id = state.uuid.generateUuid();
        bh.consume(id);
    }

    @Benchmark
    @Measurement(batchSize = 1000000)
    @Threads(4)
    public void benchmark_4(BenchmarkState state, Blackhole bh) {
        String id = state.uuid.generateUuid();
        bh.consume(id);
    }

    @Benchmark
    @Measurement(batchSize = 1000000)
    @Threads(8)
    public void benchmark_8(BenchmarkState state, Blackhole bh) {
        String id = state.uuid.generateUuid();
        bh.consume(id);
    }

    @Benchmark
    @Measurement(batchSize = 1000000)
    @Threads(16)
    public void benchmark_16(BenchmarkState state, Blackhole bh) {
        String id = state.uuid.generateUuid();
        bh.consume(id);
    }

    @Benchmark
    @Measurement(batchSize = 1000000)
    @Threads(32)
    public void benchmark_32(BenchmarkState state, Blackhole bh) {
        String id = state.uuid.generateUuid();
        bh.consume(id);
    }
}

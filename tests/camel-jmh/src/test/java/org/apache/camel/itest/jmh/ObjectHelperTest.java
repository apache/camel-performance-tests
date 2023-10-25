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

import java.util.concurrent.TimeUnit;

import org.apache.camel.support.ObjectHelper;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;

@State(Scope.Thread)
public class ObjectHelperTest {

    private String numericString = "123456789";
    private String numericFloatSmall = "123456789.0";
    private String numericFloatLarge = "123456789.0000123456789";

    private String negativeNumericString = "-123456789";
    private String negativeNumericFloatSmall = "-123456789.0";
    private String negativeNumericFloatLarge = "-123456789.0000123456789";

    private String nonNumericString = "ABCD";


    @Test
    public void launchBenchmark() throws Exception {
        Options opt = new OptionsBuilder()
                // Specify which benchmarks to run.
                // You can be more specific if you'd like to run only one benchmark per test.
                .include(this.getClass().getName() + ".*")
                // Set the following options as needed
                .measurementIterations(10)
                .warmupIterations(5)
                .forks(1)
                .resultFormat(ResultFormatType.JSON)
                .result(this.getClass().getSimpleName() + ".jmh.json")
                .build();
        new Runner(opt).run();
    }


    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsNumberInteger(Blackhole bh) {
        bh.consume(ObjectHelper.isNumber(numericString));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsNumberNegativeInteger(Blackhole bh) {
        bh.consume(ObjectHelper.isNumber(negativeNumericString));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsNumberFloatSmall(Blackhole bh) {
        bh.consume(ObjectHelper.isNumber(numericFloatSmall));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsNumberNonNumeric(Blackhole bh) {
        bh.consume(ObjectHelper.isNumber(nonNumericString));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsFloatingNumberNonNumeric(Blackhole bh) {
        bh.consume(ObjectHelper.isFloatingNumber(nonNumericString));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsFloatingNumberInteger(Blackhole bh) {
        bh.consume(ObjectHelper.isFloatingNumber(numericString));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsFloatingNumberNumericFloatSmall(Blackhole bh) {
        bh.consume(ObjectHelper.isFloatingNumber(numericFloatSmall));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsFloatingNumberNumericFloatLarge(Blackhole bh) {
        bh.consume(ObjectHelper.isFloatingNumber(numericFloatLarge));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsFloatingNumberNegativeNumericFloatSmall(Blackhole bh) {
        bh.consume(ObjectHelper.isFloatingNumber(negativeNumericFloatSmall));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsFloatingNumberNegativeNumericFloatLarge(Blackhole bh) {
        bh.consume(ObjectHelper.isFloatingNumber(negativeNumericFloatLarge));
    }
}

package org.apache.camel.itest.jmh;

import java.util.concurrent.TimeUnit;

import org.apache.camel.util.StringHelper;
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
public class StringHelperTest {

    private String stringWithQuotes = "\"The quick brown fox jumps over the lazy dog\"";

    private String stringToEncode = "<The quick brown fox jumps over the lazy dog>";

    private String stringToCapitalize = "property";

    private String dashStringToCapitalizePositive = "property-name";

    private String dashStringToCapitalizeNegative = "property";

    private String camelCaseToDashStringToCapitalize = "propertyName";

    private String replaceableText = "part1.secondPart";

    private String sanitazableText = "part1.secondPart://something";

    private String nonSanitazableText = "part1SecondPartSomething";

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
    public void testFillChar(Blackhole bh) {
        bh.consume(StringHelper.fillChars('t', 32));
    }


    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testFillCharNative(Blackhole bh) {
        bh.consume(Character.toString('t').repeat(32));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testRemoveQuotes(Blackhole bh) {
        bh.consume(StringHelper.removeQuotes(stringWithQuotes));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testXmlEncode(Blackhole bh) {
        bh.consume(StringHelper.xmlEncode(stringToEncode));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testRemoveLeadingAndEndingQuotes(Blackhole bh) {
        bh.consume(StringHelper.removeLeadingAndEndingQuotes(stringWithQuotes));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsClassNameNegative(Blackhole bh) {
        bh.consume(StringHelper.isClassName(stringWithQuotes));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testIsClassNamePositive(Blackhole bh) {
        bh.consume(StringHelper.isClassName(bh.getClass().getName()));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testCapitalize(Blackhole bh) {
        bh.consume(StringHelper.capitalize(stringWithQuotes));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testDashToCamelCasePositive(Blackhole bh) {
        bh.consume(StringHelper.dashToCamelCase(dashStringToCapitalizePositive));
    }


    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testDashToCamelCaseNegative(Blackhole bh) {
        bh.consume(StringHelper.dashToCamelCase(dashStringToCapitalizeNegative));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testDashToCamelCasePositiveSkip(Blackhole bh) {
        bh.consume(StringHelper.dashToCamelCase(dashStringToCapitalizePositive, true));
    }


    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testDashToCamelCaseNegativeSkip(Blackhole bh) {
        bh.consume(StringHelper.dashToCamelCase(dashStringToCapitalizeNegative, true));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testCamelCaseToDashPositive(Blackhole bh) {
        bh.consume(StringHelper.camelCaseToDash(camelCaseToDashStringToCapitalize));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testCamelCaseToDashNegative(Blackhole bh) {
        bh.consume(StringHelper.camelCaseToDash(dashStringToCapitalizeNegative));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testReplaceFirst(Blackhole bh) {
        bh.consume(StringHelper.replaceFirst(replaceableText, "part1", "firstPart"));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testSanitizeNegative(Blackhole bh) {
        bh.consume(StringHelper.sanitize(nonSanitazableText));
    }

    @Benchmark
    @BenchmarkMode(Mode.AverageTime)
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    public void testSanitizePositive(Blackhole bh) {
        bh.consume(StringHelper.sanitize(sanitazableText));
    }

}

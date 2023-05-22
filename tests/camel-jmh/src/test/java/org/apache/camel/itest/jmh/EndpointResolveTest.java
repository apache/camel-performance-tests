package org.apache.camel.itest.jmh;

import java.util.concurrent.TimeUnit;

import org.apache.camel.CamelContext;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.ServiceStatus;
import org.apache.camel.impl.DefaultCamelContext;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Threads;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;

/**
 * This test computes the accumulated time of all the operations required to resolve the same route over and over.
 */
public class EndpointResolveTest {

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

    @State(Scope.Benchmark)
    public static class BenchmarkState {
        CamelContext context;
        ProducerTemplate producerTemplate;

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            context = new DefaultCamelContext();

            context.start();
            producerTemplate = context.createProducerTemplate();
        }
    }


    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    public void testActionStatus_1(BenchmarkState state, Blackhole bh) {
        Object reply = state.producerTemplate.requestBody("controlbus:route?routeId=route1&action=status&loggingLevel=off", null,
                ServiceStatus.class);

        bh.consume(reply);
    }


    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    @Threads(2)
    public void testActionStatus_2(BenchmarkState state, Blackhole bh) {
        Object reply = state.producerTemplate.requestBody("controlbus:route?routeId=route1&action=status&loggingLevel=off", null,
                ServiceStatus.class);

        bh.consume(reply);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    @Threads(4)
    public void testActionStatus_4(BenchmarkState state, Blackhole bh) {
        Object reply = state.producerTemplate.requestBody("controlbus:route?routeId=route1&action=status&loggingLevel=off", null,
                ServiceStatus.class);

        bh.consume(reply);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    @Threads(8)
    public void testActionStatus_8(BenchmarkState state, Blackhole bh) {
        Object reply = state.producerTemplate.requestBody("controlbus:route?routeId=route1&action=status&loggingLevel=off", null,
                ServiceStatus.class);

        bh.consume(reply);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    @Threads(16)
    public void testActionStatus_16(BenchmarkState state, Blackhole bh) {
        Object reply = state.producerTemplate.requestBody("controlbus:route?routeId=route1&action=status&loggingLevel=off", null,
                ServiceStatus.class);

        bh.consume(reply);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    @Threads(32)
    public void testActionStatus_32(BenchmarkState state, Blackhole bh) {
        Object reply = state.producerTemplate.requestBody("controlbus:route?routeId=route1&action=status&loggingLevel=off", null,
                ServiceStatus.class);

        bh.consume(reply);
    }
}

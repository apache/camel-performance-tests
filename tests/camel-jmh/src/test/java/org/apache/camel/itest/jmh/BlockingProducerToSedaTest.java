package org.apache.camel.itest.jmh;

import java.io.File;
import java.util.concurrent.TimeUnit;

import org.apache.camel.CamelContext;
import org.apache.camel.Endpoint;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.builder.RouteBuilder;
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

public class BlockingProducerToSedaTest {

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

    // The JMH samples are the best documentation for how to use it
    // http://hg.openjdk.java.net/code-tools/jmh/file/tip/jmh-samples/src/main/java/org/openjdk/jmh/samples/
    @State(Scope.Benchmark)
    public static class BenchmarkState {

        CamelContext context;
        ProducerTemplate producerTemplate;
        Endpoint endpoint;

        File sampleFile = new File("some-file");
        Integer someInt = Integer.valueOf(1);
        Long someLong = Long.valueOf(2);

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            context = new DefaultCamelContext();

            producerTemplate = context.createProducerTemplate();
            endpoint = context.getEndpoint("seda:test?blockWhenFull=true&offerTimeout=1000");

            context.addRoutes(new RouteBuilder() {
                @Override
                public void configure() {
                    onException(IllegalStateException.class)
                            .process(e -> System.out.println("The SEDA queue is likely full and the system may be unable to catch to the load. Fix the test parameters"));

                    fromF("seda:test").to("log:?level=OFF");

                }
            });

            context.start();
        }
    }

    @OutputTimeUnit(TimeUnit.MILLISECONDS)
    @BenchmarkMode({Mode.Throughput, Mode.AverageTime, Mode.SingleShotTime})
    @Benchmark
    public void sendBlocking(BenchmarkState state, Blackhole bh) {
        state.producerTemplate.sendBody(state.endpoint, "test");
    }

    @OutputTimeUnit(TimeUnit.MILLISECONDS)
    @BenchmarkMode({Mode.Throughput, Mode.AverageTime, Mode.SingleShotTime})
    @Benchmark
    @Threads(6)
    public void sendBlocking_6(BenchmarkState state, Blackhole bh) {
        state.producerTemplate.sendBody(state.endpoint, "test");
    }


    @OutputTimeUnit(TimeUnit.MILLISECONDS)
    @BenchmarkMode({Mode.Throughput, Mode.AverageTime, Mode.SingleShotTime})
    @Benchmark
    public void sendBlockingWithMultipleTypes(BenchmarkState state, Blackhole bh) {
        state.producerTemplate.sendBody(state.endpoint, "test");
        state.producerTemplate.sendBody(state.endpoint, state.someInt);
        state.producerTemplate.sendBody(state.endpoint, state.someLong);
        state.producerTemplate.sendBody(state.endpoint, state.sampleFile);
    }

    @OutputTimeUnit(TimeUnit.MILLISECONDS)
    @BenchmarkMode({Mode.Throughput, Mode.AverageTime, Mode.SingleShotTime})
    @Benchmark
    @Threads(6)
    public void sendBlockingWithMultipleTypes_6(BenchmarkState state, Blackhole bh) {
        state.producerTemplate.sendBody(state.endpoint, "test");
        state.producerTemplate.sendBody(state.endpoint, state.someInt);
        state.producerTemplate.sendBody(state.endpoint, state.someLong);
        state.producerTemplate.sendBody(state.endpoint, state.sampleFile);
    }


}

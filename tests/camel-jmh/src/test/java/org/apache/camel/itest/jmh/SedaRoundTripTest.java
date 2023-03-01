package org.apache.camel.itest.jmh;

import java.io.File;
import java.util.concurrent.TimeUnit;

import org.apache.camel.CamelContext;
import org.apache.camel.ConsumerTemplate;
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
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;

public class SedaRoundTripTest {

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
        ConsumerTemplate consumerTemplate;
        Endpoint producerEndpoint;
        Endpoint consumerEndpoint;

        String someString = "test1";
        File sampleFile = new File("some-file");
        Integer someInt = Integer.valueOf(1);
        Long someLong = Long.valueOf(2);

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            context = new DefaultCamelContext();

            producerTemplate = context.createProducerTemplate();
            consumerTemplate = context.createConsumerTemplate();

            producerEndpoint = context.getEndpoint("seda:test?blockWhenFull=true&offerTimeout=1000");
            consumerEndpoint = context.getEndpoint("seda:test");

            context.start();
        }
    }

    @OutputTimeUnit(TimeUnit.MILLISECONDS)
    @BenchmarkMode({Mode.Throughput, Mode.AverageTime, Mode.SingleShotTime})
    @Benchmark
    public void sendBlocking(SedaRoundTripTest.BenchmarkState state, Blackhole bh) {
        state.producerTemplate.sendBody(state.producerEndpoint, state.someString);
        bh.consume(state.consumerTemplate.receive(state.consumerEndpoint));
    }


    @OutputTimeUnit(TimeUnit.MILLISECONDS)
    @BenchmarkMode({Mode.Throughput, Mode.AverageTime, Mode.SingleShotTime})
    @Benchmark
    public void sendBlockingWithMultipleTypes(SedaRoundTripTest.BenchmarkState state, Blackhole bh) {
        state.producerTemplate.sendBody(state.producerEndpoint, state.someString);
        bh.consume(state.consumerTemplate.receive(state.consumerEndpoint));

        state.producerTemplate.sendBody(state.producerEndpoint, state.someLong);
        bh.consume(state.consumerTemplate.receive(state.consumerEndpoint));

        state.producerTemplate.sendBody(state.producerEndpoint, state.someInt);
        bh.consume(state.consumerTemplate.receive(state.consumerEndpoint));

        state.producerTemplate.sendBody(state.producerEndpoint, state.sampleFile);
        bh.consume(state.consumerTemplate.receive(state.consumerEndpoint));
    }


}

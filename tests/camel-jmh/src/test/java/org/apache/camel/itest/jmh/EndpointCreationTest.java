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
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;

/**
 * This test computes the accumulated time of all the operations required to create a given number of routes (500, in this test).
 */
public class EndpointCreationTest {

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

    @State(Scope.Thread)
    public static class BenchmarkState {
        CamelContext context;
        ProducerTemplate producerTemplate;
        String[] routes = new String[500];

        @Setup(Level.Iteration)
        public void initialize() throws Exception {
            context = new DefaultCamelContext();

            context.start();
            producerTemplate = context.createProducerTemplate();

            for (int i = 0; i < routes.length; i++) {
                routes[i] = "controlbus:route?routeId=route" + i + "&action=status&loggingLevel=off";
            }
        }
    }


    @OutputTimeUnit(TimeUnit.MILLISECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    public void testCreation(BenchmarkState state, Blackhole bh) {
        for (String route : state.routes) {
            Object reply = state.producerTemplate.requestBody(route, null,
                    ServiceStatus.class);

            bh.consume(reply);
        }
    }
}

package org.apache.camel.itest.jmh;

import java.util.concurrent.TimeUnit;

import org.apache.camel.Endpoint;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.ServiceStatus;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.spi.EndpointRegistry;
import org.apache.camel.support.NormalizedUri;
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
 * These tests specific operations of the Endpoint registry in single-thread scenarios.
 */
public class EndpointRegistryTest {

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
        DefaultCamelContext context;
        ProducerTemplate producerTemplate;
        EndpointRegistry<NormalizedUri> endpointRegistry;

        NormalizedUri[] routes = new NormalizedUri[500];
        NormalizedUri[] nonExistentRoutes = new NormalizedUri[500];
        Endpoint[] endpoints = new Endpoint[500];

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            context = new DefaultCamelContext();

            context.start();
            producerTemplate = context.createProducerTemplate();
            endpointRegistry = context.getEndpointRegistry();

            for (int i = 0; i < routes.length; i++) {
                String route = "controlbus:route?routeId=route" + i + "&action=status&loggingLevel=off";
                routes[i] = NormalizedUri.newNormalizedUri(route, false);

                endpoints[i] = context.getEndpoint(route);
                producerTemplate.requestBody(endpoints[i], null, ServiceStatus.class);

                nonExistentRoutes[i] = NormalizedUri.newNormalizedUri("controlbus:route?routeId=nonExistentRoutes" + i + "&action=status&loggingLevel=off",
                    false);

            }
        }
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    public void testContainsExistentKey(BenchmarkState state, Blackhole bh) {
        for (NormalizedUri route : state.routes) {
            bh.consume(state.endpointRegistry.containsKey(route));
        }
    }


    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    public void testContainsNonExistentKey(BenchmarkState state, Blackhole bh) {
        for (NormalizedUri route : state.nonExistentRoutes) {
            bh.consume(state.endpointRegistry.containsKey(route));
        }
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    public void testContainsNonExistentValue(BenchmarkState state, Blackhole bh) {
        for (Endpoint ep : state.endpoints) {
            bh.consume(state.endpointRegistry.containsValue(ep));
        }
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    public void testIsDynamic(BenchmarkState state, Blackhole bh) {
        for (NormalizedUri route : state.routes) {
            bh.consume(state.endpointRegistry.isDynamic(route.get()));
        }
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    public void testDynamicSize(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.dynamicSize());
    }

    // The following methods require camel 4.0.0-M2 or newer. Comment these if running w/ 4.0.0-M1 or 3.x
    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    public void testReadOnlyMap(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.getReadOnlyMap());
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    public void testReadOnlyValues(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.getReadOnlyValues());
    }
}

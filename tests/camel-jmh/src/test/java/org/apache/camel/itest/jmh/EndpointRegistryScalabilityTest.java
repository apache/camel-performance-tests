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
import org.openjdk.jmh.annotations.Threads;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;

/**
 * These tests specific operations of the Endpoint registry in multi-thread scenarios.
 */
public class EndpointRegistryScalabilityTest {

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


    private static void doContainsCheck(BenchmarkState state, Blackhole bh) {
        for (NormalizedUri route : state.routes) {
            bh.consume(state.endpointRegistry.containsKey(route));
        }
    }


    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(2)
    @Benchmark
    public void testContainsNonExistentKey_2(BenchmarkState state, Blackhole bh) {
        doContainsCheck(state, bh);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(4)
    @Benchmark
    public void testContainsNonExistentKey_4(BenchmarkState state, Blackhole bh) {
        doContainsCheck(state, bh);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(8)
    @Benchmark
    public void testContainsNonExistentKey_8(BenchmarkState state, Blackhole bh) {
        doContainsCheck(state, bh);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(2)
    @Benchmark
    public void testContainsNonExistentValue_2(BenchmarkState state, Blackhole bh) {
        doContainsValueCheck(state, bh);
    }

    private static void doContainsValueCheck(BenchmarkState state, Blackhole bh) {
        for (Endpoint ep : state.endpoints) {
            bh.consume(state.endpointRegistry.containsValue(ep));
        }
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(4)
    @Benchmark
    public void testContainsNonExistentValue_4(BenchmarkState state, Blackhole bh) {
        doContainsValueCheck(state, bh);
    }


    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(8)
    @Benchmark
    public void testContainsNonExistentValue_8(BenchmarkState state, Blackhole bh) {
        doContainsValueCheck(state, bh);
    }

    private static void doIsDynamicCheck(BenchmarkState state, Blackhole bh) {
        for (NormalizedUri route : state.routes) {
            bh.consume(state.endpointRegistry.isDynamic(route.get()));
        }
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(2)
    @Benchmark
    public void testIsDynamic_2(BenchmarkState state, Blackhole bh) {
        doIsDynamicCheck(state, bh);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(4)
    @Benchmark
    public void testIsDynamic_4(BenchmarkState state, Blackhole bh) {
        doIsDynamicCheck(state, bh);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(8)
    @Benchmark
    public void testIsDynamic_8(BenchmarkState state, Blackhole bh) {
        doIsDynamicCheck(state, bh);
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(2)
    @Benchmark
    public void testDynamicSize_2(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.dynamicSize());
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(4)
    @Benchmark
    public void testDynamicSize_4(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.dynamicSize());
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(8)
    @Benchmark
    public void testDynamicSize_8(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.dynamicSize());
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(2)
    @Benchmark
    public void testReadOnlyMap_2(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.getReadOnlyMap());
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(4)
    @Benchmark
    public void testReadOnlyMap_4(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.getReadOnlyMap());
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(8)
    @Benchmark
    public void testReadOnlyMap_8(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.getReadOnlyMap());
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(2)
    @Benchmark
    public void testReadOnlyValues_2(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.getReadOnlyValues());
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(4)
    @Benchmark
    public void testReadOnlyValues_4(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.getReadOnlyValues());
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Threads(8)
    @Benchmark
    public void testReadOnlyValues_8(BenchmarkState state, Blackhole bh) {
        bh.consume(state.endpointRegistry.getReadOnlyValues());
    }
}

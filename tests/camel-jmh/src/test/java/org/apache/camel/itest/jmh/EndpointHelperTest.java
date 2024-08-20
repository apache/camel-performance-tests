package org.apache.camel.itest.jmh;

import java.util.concurrent.TimeUnit;

import org.apache.camel.Endpoint;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.ServiceStatus;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.spi.EndpointRegistry;
import org.apache.camel.support.EndpointHelper;
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
 * These tests specific operations of the EndpointHelper in single-thread scenarios.
 */
public class EndpointHelperTest {

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
        EndpointRegistry endpointRegistry;

        String[] stringRoutes = new String[500];
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
                final String route = "controlbus:route?routeId=route" + i + "&action=status&loggingLevel=off";

                stringRoutes[i] = route;
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
    public void testMatchEndpointSame(BenchmarkState state, Blackhole bh) {
        for (String route : state.stringRoutes) {
            bh.consume(EndpointHelper.matchEndpoint(state.context, route, route));
        }
    }


    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @BenchmarkMode(Mode.AverageTime)
    @Benchmark
    public void testMatchEndpointNotSame(BenchmarkState state, Blackhole bh) {
        for (int i = 0; i < state.routes.length; i++) {
            bh.consume(EndpointHelper.matchEndpoint(state.context, state.routes[i].toString(), state.stringRoutes[i]));
        }
    }

}

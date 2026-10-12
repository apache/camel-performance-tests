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
package org.apache.camel.itest.jmh.groovy;

import java.util.Map;
import java.util.concurrent.atomic.LongAdder;

import org.apache.camel.CamelContext;
import org.apache.camel.Endpoint;
import org.apache.camel.Exchange;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.builder.RouteBuilder;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.support.ExpressionAdapter;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.annotations.Threads;
import org.openjdk.jmh.runner.Runner;

import static org.apache.camel.itest.jmh.groovy.GroovyBenchmarkSupport.check;

/**
 * Scenario 4: full route direct -> filter -> setBody -> counting processor via ProducerTemplate, with the filter and
 * setBody written in Java, groovy, simple, jactl, java (jOOR), mvel, js (GraalJS), python3 (GraalPy) and quickjs
 * (QuickJS4J).
 */
public class GroovyRouteTest {

    // endpoint name -> { language, filter predicate, setBody expression }
    static final Map<String, String[]> SCRIPTS = Map.of(
            "groovy", new String[] { "groovy", "headers.amount > 100", "body + '-' + header.foo" },
            "simple", new String[] { "simple", "${header.amount} > 100", "${body}-${header.foo}" },
            "jactl", new String[] { "jactl", "headers.amount > 100", "body + '-' + headers.foo" },
            "javaLanguage", new String[] {
                    "java", "headerAs('amount', Integer) > 100", "bodyAs(String) + '-' + headerAs('foo', String)" },
            "mvel", new String[] { "mvel", "headers.amount > 100", "request.body + '-' + headers.foo" },
            "js", new String[] { "js", "headers.get('amount') > 100", "body + '-' + headers.get('foo')" },
            "python3", new String[] { "python3", "headers['amount'] > 100", "body + '-' + headers['foo']" },
            "quickjs", new String[] { "quickjs", "headers.amount > 100", "body + '-' + headers.foo" });

    @Test
    public void launchBenchmark() throws Exception {
        new Runner(GroovyBenchmarkSupport.options(getClass(), "thrpt").build()).run();
    }

    @State(Scope.Benchmark)
    public static class BenchmarkState {
        final LongAdder counter = new LongAdder();
        final Map<String, Object> headers = Map.of("amount", 150, "foo", "Camel");
        CamelContext camel;
        ProducerTemplate template;
        Endpoint java;
        Endpoint groovy;
        Endpoint simple;
        Endpoint jactl;
        Endpoint javaLanguage;
        Endpoint mvel;
        Endpoint js;
        Endpoint python3;
        Endpoint quickjs;

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            camel = new DefaultCamelContext();
            camel.addRoutes(new RouteBuilder() {
                @Override
                public void configure() {
                    from("direct:java").routeId("java")
                            .filter(e -> e.getMessage().getHeader("amount", Integer.class) > 100)
                            .setBody(new ExpressionAdapter() {
                                @Override
                                public Object evaluate(Exchange e) {
                                    return e.getMessage().getBody(String.class) + "-"
                                           + e.getMessage().getHeader("foo", String.class);
                                }
                            })
                            .process(e -> counter.increment());

                    for (Map.Entry<String, String[]> entry : SCRIPTS.entrySet()) {
                        String[] script = entry.getValue();
                        from("direct:" + entry.getKey()).routeId(entry.getKey())
                                .filter().language(script[0], script[1])
                                .setBody().language(script[0], script[2])
                                .process(e -> counter.increment());
                    }
                }
            });
            camel.start();
            template = camel.createProducerTemplate();
            java = camel.getEndpoint("direct:java");
            groovy = camel.getEndpoint("direct:groovy");
            simple = camel.getEndpoint("direct:simple");
            jactl = camel.getEndpoint("direct:jactl");
            javaLanguage = camel.getEndpoint("direct:javaLanguage");
            mvel = camel.getEndpoint("direct:mvel");
            js = camel.getEndpoint("direct:js");
            python3 = camel.getEndpoint("direct:python3");
            quickjs = camel.getEndpoint("direct:quickjs");

            Map<String, Object> low = Map.of("amount", 50, "foo", "Camel");
            for (Endpoint endpoint : new Endpoint[] {
                    java, groovy, simple, jactl, javaLanguage, mvel, js, python3, quickjs }) {
                check(endpoint.getEndpointUri(), "World-Camel", template.requestBodyAndHeaders(endpoint, "World", headers));
                check(endpoint.getEndpointUri() + "(50)", "World", template.requestBodyAndHeaders(endpoint, "World", low));
            }
        }

        @TearDown(Level.Trial)
        public void close() {
            template.stop();
            camel.stop();
        }
    }

    @Benchmark
    @Threads(1)
    public void javaRoute1Thread(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.java, "World", state.headers);
    }

    @Benchmark
    @Threads(1)
    public void groovyRoute1Thread(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.groovy, "World", state.headers);
    }

    @Benchmark
    @Threads(1)
    public void simpleRoute1Thread(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.simple, "World", state.headers);
    }

    @Benchmark
    @Threads(1)
    public void jactlRoute1Thread(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.jactl, "World", state.headers);
    }

    @Benchmark
    @Threads(1)
    public void javaLanguageRoute1Thread(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.javaLanguage, "World", state.headers);
    }

    @Benchmark
    @Threads(1)
    public void mvelRoute1Thread(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.mvel, "World", state.headers);
    }

    @Benchmark
    @Threads(1)
    public void jsRoute1Thread(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.js, "World", state.headers);
    }

    @Benchmark
    @Threads(1)
    public void python3Route1Thread(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.python3, "World", state.headers);
    }

    @Benchmark
    @Threads(1)
    public void quickjsRoute1Thread(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.quickjs, "World", state.headers);
    }

    @Benchmark
    @Threads(8)
    public void javaRoute8Threads(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.java, "World", state.headers);
    }

    @Benchmark
    @Threads(8)
    public void groovyRoute8Threads(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.groovy, "World", state.headers);
    }

    @Benchmark
    @Threads(8)
    public void simpleRoute8Threads(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.simple, "World", state.headers);
    }

    @Benchmark
    @Threads(8)
    public void jactlRoute8Threads(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.jactl, "World", state.headers);
    }

    @Benchmark
    @Threads(8)
    public void javaLanguageRoute8Threads(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.javaLanguage, "World", state.headers);
    }

    @Benchmark
    @Threads(8)
    public void mvelRoute8Threads(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.mvel, "World", state.headers);
    }

    @Benchmark
    @Threads(8)
    public void jsRoute8Threads(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.js, "World", state.headers);
    }

    @Benchmark
    @Threads(8)
    public void python3Route8Threads(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.python3, "World", state.headers);
    }

    @Benchmark
    @Threads(8)
    public void quickjsRoute8Threads(BenchmarkState state) {
        state.template.sendBodyAndHeaders(state.quickjs, "World", state.headers);
    }
}

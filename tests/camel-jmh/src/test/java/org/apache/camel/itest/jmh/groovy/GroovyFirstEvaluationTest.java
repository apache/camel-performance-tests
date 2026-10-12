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

import java.util.concurrent.atomic.AtomicInteger;

import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.spi.Language;
import org.apache.camel.support.DefaultExchange;
import org.apache.camel.support.ExpressionAdapter;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.runner.Runner;

/**
 * Scenario 5a: first-evaluation latency (create + evaluate) of the same expression in every language. Every invocation
 * gets a new CamelContext (untimed) and a script text that was never compiled before (the number in a comment). With 0
 * warmup iterations the first measured iteration of each fork is JVM-cold (compiler / polyglot engine not loaded yet);
 * later iterations show the cost on a warm JVM. Use the rawData in the JSON result to split them. Languages: Java,
 * simple, groovy, jactl, java (jOOR), mvel, js (GraalJS), python3 (GraalPy) and quickjs (QuickJS4J).
 */
public class GroovyFirstEvaluationTest {

    @Test
    public void launchBenchmark() throws Exception {
        new Runner(GroovyBenchmarkSupport.options(getClass(), "ss", 10, 0, 1, 20, 1).build()).run();
    }

    @State(Scope.Thread)
    public static class ColdState {
        static final AtomicInteger COUNTER = new AtomicInteger();

        CamelContext camel;
        Exchange exchange;
        Language simple;
        Language groovy;
        Language jactl;
        Language java;
        Language mvel;
        Language js;
        Language python3;
        Language quickjs;
        int n;

        @Setup(Level.Invocation)
        public void initialize() throws Exception {
            camel = new DefaultCamelContext();
            camel.start();
            exchange = new DefaultExchange(camel);
            exchange.getIn().setBody("World");
            exchange.getIn().setHeader("foo", "Camel");
            simple = camel.resolveLanguage("simple");
            groovy = camel.resolveLanguage("groovy");
            jactl = camel.resolveLanguage("jactl");
            java = camel.resolveLanguage("java");
            mvel = camel.resolveLanguage("mvel");
            js = camel.resolveLanguage("js");
            python3 = camel.resolveLanguage("python3");
            quickjs = camel.resolveLanguage("quickjs");
            n = COUNTER.incrementAndGet();
        }

        @TearDown(Level.Invocation)
        public void close() {
            camel.stop();
        }

        Object evaluate(Language language, String script) {
            var expression = language.createExpression(script);
            expression.init(camel);
            return expression.evaluate(exchange, String.class);
        }
    }

    @Benchmark
    public void firstEvaluationJava(ColdState state, Blackhole bh) {
        ExpressionAdapter expression = new ExpressionAdapter() {
            @Override
            public Object evaluate(Exchange e) {
                return e.getMessage().getBody(String.class) + "-" + e.getMessage().getHeader("foo", String.class);
            }
        };
        expression.init(state.camel);
        bh.consume(expression.evaluate(state.exchange, String.class));
    }

    @Benchmark
    public void firstEvaluationSimple(ColdState state, Blackhole bh) {
        bh.consume(state.evaluate(state.simple, "${body}-${header.foo}"));
    }

    @Benchmark
    public void firstEvaluationGroovy(ColdState state, Blackhole bh) {
        bh.consume(state.evaluate(state.groovy, "body + '-' + header.foo // " + state.n));
    }

    @Benchmark
    public void firstEvaluationJactl(ColdState state, Blackhole bh) {
        bh.consume(state.evaluate(state.jactl, "body + '-' + headers.foo // " + state.n));
    }

    @Benchmark
    public void firstEvaluationJavaLanguage(ColdState state, Blackhole bh) {
        // leading comment: jOOR wraps a single expression in "return ...;"
        bh.consume(state.evaluate(state.java, "/* " + state.n + " */ bodyAs(String) + '-' + headerAs('foo', String)"));
    }

    @Benchmark
    public void firstEvaluationMvel(ColdState state, Blackhole bh) {
        bh.consume(state.evaluate(state.mvel, "/* " + state.n + " */ request.body + '-' + headers.foo"));
    }

    @Benchmark
    public void firstEvaluationJs(ColdState state, Blackhole bh) {
        bh.consume(state.evaluate(state.js, "/* " + state.n + " */ body + '-' + headers.get('foo')"));
    }

    @Benchmark
    public void firstEvaluationPython3(ColdState state, Blackhole bh) {
        bh.consume(state.evaluate(state.python3, "body + '-' + headers['foo'] # " + state.n));
    }

    @Benchmark
    public void firstEvaluationQuickjs(ColdState state, Blackhole bh) {
        bh.consume(state.evaluate(state.quickjs, "/* " + state.n + " */ body + '-' + headers.foo"));
    }
}

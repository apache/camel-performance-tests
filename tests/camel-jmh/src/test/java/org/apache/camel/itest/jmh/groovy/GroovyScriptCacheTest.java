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
import org.apache.camel.Expression;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.spi.Language;
import org.apache.camel.support.DefaultExchange;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.runner.Runner;

/**
 * Scenario 5b/5c: cost of compiling N distinct scripts, and steady-state behaviour when a context uses more distinct
 * scripts than the 1000 entry script cache can hold. Run with {@code -Djmh.prof=gc|cl} to see class loading churn.
 */
public class GroovyScriptCacheTest {

    static final AtomicInteger COUNTER = new AtomicInteger();

    @Test
    public void launchBenchmark() throws Exception {
        new Runner(GroovyBenchmarkSupport.options(getClass(), "avgt").build()).run();
    }

    static Exchange exchange(CamelContext camel) {
        Exchange exchange = new DefaultExchange(camel);
        exchange.getIn().setBody("World");
        exchange.getIn().setHeader("foo", "Camel");
        return exchange;
    }

    @State(Scope.Thread)
    public static class DistinctScriptsState {
        @Param({ "10", "100", "1000" })
        int scripts;

        CamelContext camel;
        Exchange exchange;
        Language groovy;
        String[] texts;

        @Setup(Level.Invocation)
        public void initialize() throws Exception {
            camel = new DefaultCamelContext();
            camel.start();
            exchange = exchange(camel);
            groovy = camel.resolveLanguage("groovy");
            int run = COUNTER.incrementAndGet();
            texts = new String[scripts];
            for (int i = 0; i < scripts; i++) {
                texts[i] = "body + '-' + header.foo // " + run + "-" + i;
            }
        }

        @TearDown(Level.Invocation)
        public void close() {
            camel.stop();
        }
    }

    @State(Scope.Thread)
    public static class RoundRobinState {
        @Param({ "100", "1000", "1001", "2000" })
        int distinctScripts;

        CamelContext camel;
        Exchange exchange;
        Expression[] expressions;
        int index;

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            camel = new DefaultCamelContext();
            camel.start();
            exchange = exchange(camel);
            Language groovy = camel.resolveLanguage("groovy");
            expressions = new Expression[distinctScripts];
            for (int i = 0; i < distinctScripts; i++) {
                expressions[i] = groovy.createExpression("body + '-' + header.foo // " + i);
                // fill the cache
                GroovyBenchmarkSupport.check("script " + i, "World-Camel", expressions[i].evaluate(exchange, String.class));
            }
        }

        @TearDown(Level.Trial)
        public void close() {
            camel.stop();
        }
    }

    /**
     * Compiles and evaluates N scripts that were never seen before (one CamelContext per invocation).
     */
    @Benchmark
    @BenchmarkMode(Mode.SingleShotTime)
    public void compileDistinctScripts(DistinctScriptsState state, Blackhole bh) {
        for (String text : state.texts) {
            bh.consume(state.groovy.createExpression(text).evaluate(state.exchange, String.class));
        }
    }

    /**
     * Evaluates the scripts of a context round-robin. Up to 1000 scripts every evaluation is a cache hit; beyond that the
     * cache evicts and scripts are recompiled.
     */
    @Benchmark
    public void roundRobinDistinctScripts(RoundRobinState state, Blackhole bh) {
        Expression expression = state.expressions[state.index++ % state.distinctScripts];
        bh.consume(expression.evaluate(state.exchange, String.class));
    }
}

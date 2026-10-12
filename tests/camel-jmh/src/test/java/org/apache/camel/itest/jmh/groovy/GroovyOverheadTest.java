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

import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.util.HashMap;

import groovy.lang.GroovyShell;
import groovy.lang.Script;
import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.Expression;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.language.groovy.GroovyShellFactory;
import org.apache.camel.support.DefaultExchange;
import org.apache.camel.support.ObjectHelper;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.runner.Runner;

import static org.apache.camel.itest.jmh.groovy.GroovyBenchmarkSupport.check;

/**
 * Scenario 6: registry and binding overhead of a groovy evaluation, broken down step by step, plus benchmark-local
 * prototypes of a cheaper evaluation ({@link OptimizedGroovyExpression}).
 */
public class GroovyOverheadTest {

    static final String SCRIPT = "body + '-' + header.foo";

    @Test
    public void launchBenchmark() throws Exception {
        new Runner(GroovyBenchmarkSupport.options(getClass(), "thrpt").build()).run();
    }

    static Exchange exchange(CamelContext camel) {
        Exchange exchange = new DefaultExchange(camel);
        exchange.getIn().setBody("World");
        exchange.getIn().setHeader("foo", "Camel");
        return exchange;
    }

    @State(Scope.Thread)
    public static class EvaluateState {
        @Param({ "0", "500" })
        int extraBeans;

        @Param({ "none", "factoryWithFileName" })
        String shellFactory;

        CamelContext camel;
        Exchange exchange;
        Expression groovy;
        Expression optimized;
        Expression optimizedLazyBinding;

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            camel = new DefaultCamelContext();
            for (int i = 0; i < extraBeans; i++) {
                camel.getRegistry().bind("bean" + i, i % 2 == 0 ? new Object() : "value" + i);
            }
            if ("factoryWithFileName".equals(shellFactory)) {
                camel.getRegistry().bind("shellFactory", new GroovyShellFactory() {
                    @Override
                    public GroovyShell createGroovyShell(Exchange exchange) {
                        return new GroovyShell();
                    }

                    @Override
                    public String getFileName(Exchange exchange) {
                        return "BenchmarkScript.groovy";
                    }
                });
            }
            camel.start();
            exchange = exchange(camel);
            groovy = camel.resolveLanguage("groovy").createExpression(SCRIPT);
            optimized = new OptimizedGroovyExpression(SCRIPT, false);
            optimizedLazyBinding = new OptimizedGroovyExpression(SCRIPT, true);
            for (Expression e : new Expression[] { groovy, optimized, optimizedLazyBinding }) {
                e.init(camel);
                check(e.getClass().getSimpleName(), "World-Camel", e.evaluate(exchange, String.class));
            }
        }

        @TearDown(Level.Trial)
        public void close() {
            camel.stop();
        }
    }

    @State(Scope.Thread)
    public static class StepsState {
        CamelContext camel;
        Exchange exchange;
        GroovyExpressionProbe probe;
        Class<?> scriptClass;
        MethodHandle constructor;
        Script prebuiltScript;
        String fileName = "BenchmarkScript.groovy";
        String text = SCRIPT;
        HashMap<String, Object> cache = new HashMap<>();

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            camel = new DefaultCamelContext();
            camel.start();
            exchange = exchange(camel);
            probe = new GroovyExpressionProbe(SCRIPT);
            probe.init(camel);
            scriptClass = new GroovyShell().getClassLoader().parseClass(SCRIPT);
            constructor = MethodHandles.publicLookup().findConstructor(scriptClass, MethodType.methodType(void.class))
                    .asType(MethodType.methodType(Script.class));
            prebuiltScript = ObjectHelper.newInstance(scriptClass, Script.class);
            prebuiltScript.setBinding(probe.binding(exchange, new HashMap<>()));
            cache.put(fileName + text, scriptClass);
            check("probe", "World-Camel", probe.evaluate(exchange, String.class));
            check("prebuiltScript", "World-Camel", prebuiltScript.run());
        }

        @TearDown(Level.Trial)
        public void close() {
            camel.stop();
        }
    }

    // whole evaluation with/without registry beans and a GroovyShellFactory

    @Benchmark
    public void evaluateGroovy(EvaluateState state, Blackhole bh) {
        bh.consume(state.groovy.evaluate(state.exchange, String.class));
    }

    @Benchmark
    public void evaluatePrototypeOptimized(EvaluateState state, Blackhole bh) {
        bh.consume(state.optimized.evaluate(state.exchange, String.class));
    }

    @Benchmark
    public void evaluatePrototypeLazyBinding(EvaluateState state, Blackhole bh) {
        bh.consume(state.optimizedLazyBinding.evaluate(state.exchange, String.class));
    }

    // the individual steps of GroovyExpression.evaluate

    @Benchmark
    public void stepResolveLanguage(StepsState state, Blackhole bh) {
        bh.consume(state.exchange.getContext().resolveLanguage("groovy"));
    }

    @Benchmark
    public void stepFindShellFactory(StepsState state, Blackhole bh) {
        bh.consume(state.exchange.getContext().getRegistry().findByType(GroovyShellFactory.class));
    }

    @Benchmark
    public void stepCacheKeyConcatAndLookup(StepsState state, Blackhole bh) {
        bh.consume(state.cache.get(state.fileName + state.text));
    }

    @Benchmark
    public void stepInstantiateScript(StepsState state, Blackhole bh) {
        bh.consume(state.probe.instantiate(state.exchange, new HashMap<>()));
    }

    @Benchmark
    public void stepNewInstanceReflection(StepsState state, Blackhole bh) {
        bh.consume(ObjectHelper.newInstance(state.scriptClass, Script.class));
    }

    @Benchmark
    public void stepNewInstanceMethodHandle(StepsState state, Blackhole bh) throws Throwable {
        bh.consume((Script) state.constructor.invokeExact());
    }

    @Benchmark
    public void stepCreateBinding(StepsState state, Blackhole bh) {
        bh.consume(state.probe.binding(state.exchange, new HashMap<>()));
    }

    @Benchmark
    public void stepRunScript(StepsState state, Blackhole bh) {
        bh.consume(state.prebuiltScript.run());
    }

    @Benchmark
    public void stepConvertResult(StepsState state, Blackhole bh) {
        bh.consume(state.camel.getTypeConverter().convertTo(String.class, "World-Camel"));
    }
}

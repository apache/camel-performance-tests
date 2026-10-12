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

import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.Expression;
import org.apache.camel.Predicate;
import org.apache.camel.Processor;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.spi.Language;
import org.apache.camel.support.DefaultExchange;
import org.apache.camel.support.ExpressionAdapter;
import org.graalvm.polyglot.Engine;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.TearDown;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.runner.Runner;

import static org.apache.camel.itest.jmh.groovy.GroovyBenchmarkSupport.RESULT;
import static org.apache.camel.itest.jmh.groovy.GroovyBenchmarkSupport.check;

/**
 * Scenario 1 (simple expression) and scenario 2 (predicate) with identical logic in Java, simple, groovy, jactl, java
 * (jOOR), mvel, js (GraalJS), python3 (GraalPy) and quickjs (QuickJS4J).
 * <p>
 * quickjs binds JSON snapshots of the message ({@code body}, {@code headers}, {@code properties}, {@code exchangeId})
 * instead of live Java objects, and its result comes back through Jackson.
 */
public class GroovyExpressionTest {

    @Test
    public void launchBenchmark() throws Exception {
        new Runner(GroovyBenchmarkSupport.options(getClass(), "thrpt").build()).run();
    }

    @State(Scope.Thread)
    public static class BenchmarkState {
        CamelContext camel;
        Exchange concatExchange;
        Exchange arithmeticExchange;
        Exchange predicateExchange;

        Processor javaConcatProcessor;
        Expression javaConcat;
        Expression simpleConcat;
        Expression groovyConcat;
        Expression jactlConcat;
        Expression javaLanguageConcat;
        Expression mvelConcat;
        Expression jsConcat;
        Expression python3Concat;
        Expression quickjsConcat;

        Expression javaArithmetic;
        Expression simpleArithmetic;
        Expression groovyArithmetic;
        Expression jactlArithmetic;
        Expression javaLanguageArithmetic;
        Expression mvelArithmetic;
        Expression jsArithmetic;
        Expression python3Arithmetic;
        Expression quickjsArithmetic;

        Predicate javaPredicate;
        Predicate simplePredicate;
        Predicate groovyPredicate;
        Predicate jactlPredicate;
        Predicate javaLanguagePredicate;
        Predicate mvelPredicate;
        Predicate jsPredicate;
        Predicate python3Predicate;
        Predicate quickjsPredicate;

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            camel = new DefaultCamelContext();
            camel.start();

            concatExchange = new DefaultExchange(camel);
            concatExchange.getIn().setBody("World");
            concatExchange.getIn().setHeader("foo", "Camel");

            arithmeticExchange = new DefaultExchange(camel);
            arithmeticExchange.getIn().setBody(21);

            predicateExchange = new DefaultExchange(camel);
            predicateExchange.getIn().setHeader("amount", 150);

            Language simple = camel.resolveLanguage("simple");
            Language groovy = camel.resolveLanguage("groovy");
            Language jactl = camel.resolveLanguage("jactl");
            Language java = camel.resolveLanguage("java");
            Language mvel = camel.resolveLanguage("mvel");
            Language js = camel.resolveLanguage("js");
            Language python3 = camel.resolveLanguage("python3");
            Language quickjs = camel.resolveLanguage("quickjs");

            javaConcatProcessor = e -> e.setProperty(RESULT,
                    e.getMessage().getBody(String.class) + "-" + e.getMessage().getHeader("foo", String.class));
            javaConcat = new ExpressionAdapter() {
                @Override
                public Object evaluate(Exchange e) {
                    return e.getMessage().getBody(String.class) + "-" + e.getMessage().getHeader("foo", String.class);
                }
            };
            simpleConcat = simple.createExpression("${body}-${header.foo}");
            groovyConcat = groovy.createExpression("body + '-' + header.foo");
            jactlConcat = jactl.createExpression("body + '-' + headers.foo");
            javaLanguageConcat = java.createExpression("bodyAs(String) + '-' + headerAs('foo', String)");
            mvelConcat = mvel.createExpression("request.body + '-' + headers.foo");
            jsConcat = js.createExpression("body + '-' + headers.get('foo')");
            python3Concat = python3.createExpression("body + '-' + headers['foo']");
            quickjsConcat = quickjs.createExpression("body + '-' + headers.foo");

            javaArithmetic = new ExpressionAdapter() {
                @Override
                public Object evaluate(Exchange e) {
                    return e.getMessage().getBody(Integer.class) * 2 + 1;
                }
            };
            // simple has no multiply operator, body + body + 1 is the same computation
            simpleArithmetic = simple.createExpression("${sum(${body},${body},1)}");
            groovyArithmetic = groovy.createExpression("body * 2 + 1");
            jactlArithmetic = jactl.createExpression("body * 2 + 1");
            javaLanguageArithmetic = java.createExpression("bodyAs(Integer) * 2 + 1");
            mvelArithmetic = mvel.createExpression("request.body * 2 + 1");
            jsArithmetic = js.createExpression("body * 2 + 1");
            python3Arithmetic = python3.createExpression("body * 2 + 1");
            quickjsArithmetic = quickjs.createExpression("body * 2 + 1");

            javaPredicate = e -> e.getMessage().getHeader("amount", Integer.class) > 100;
            simplePredicate = simple.createPredicate("${header.amount} > 100");
            groovyPredicate = groovy.createPredicate("headers.amount > 100");
            jactlPredicate = jactl.createPredicate("headers.amount > 100");
            javaLanguagePredicate = java.createPredicate("headerAs('amount', Integer) > 100");
            mvelPredicate = mvel.createPredicate("headers.amount > 100");
            jsPredicate = js.createPredicate("headers.get('amount') > 100");
            python3Predicate = python3.createPredicate("headers['amount'] > 100");
            quickjsPredicate = quickjs.createPredicate("headers.amount > 100");

            Expression[] expressions = {
                    javaConcat, simpleConcat, groovyConcat, jactlConcat, javaLanguageConcat, mvelConcat, jsConcat,
                    python3Concat, quickjsConcat, javaArithmetic, simpleArithmetic, groovyArithmetic, jactlArithmetic,
                    javaLanguageArithmetic, mvelArithmetic, jsArithmetic, python3Arithmetic, quickjsArithmetic };
            for (Expression e : expressions) {
                e.init(camel);
            }
            Predicate[] predicates = {
                    javaPredicate, simplePredicate, groovyPredicate, jactlPredicate, javaLanguagePredicate, mvelPredicate,
                    jsPredicate, python3Predicate, quickjsPredicate };
            for (Predicate p : predicates) {
                p.init(camel);
            }

            // all variants must do the same work
            javaConcatProcessor.process(concatExchange);
            check("javaConcatProcessor", "World-Camel", concatExchange.getProperty(RESULT));
            Exchange low = new DefaultExchange(camel);
            low.getIn().setHeader("amount", 50);
            int variants = predicates.length;
            for (int i = 0; i < variants; i++) {
                check("concat " + i, "World-Camel", expressions[i].evaluate(concatExchange, String.class));
                check("arithmetic " + i, 43, expressions[variants + i].evaluate(arithmeticExchange, Integer.class));
                check("predicate " + i, true, predicates[i].matches(predicateExchange));
                check("predicate(50) " + i, false, predicates[i].matches(low));
            }
            try (Engine engine = Engine.create()) {
                System.out.println("SETUP GraalVM polyglot engine implementation: " + engine.getImplementationName());
            }
        }

        @TearDown(Level.Trial)
        public void close() {
            camel.stop();
        }
    }

    // scenario 1a: string concatenation of body and header

    @Benchmark
    public void concatJavaProcessor(BenchmarkState state, Blackhole bh) throws Exception {
        state.javaConcatProcessor.process(state.concatExchange);
        bh.consume(state.concatExchange.getProperty(RESULT));
    }

    @Benchmark
    public void concatJavaExpression(BenchmarkState state, Blackhole bh) {
        concat(state, state.javaConcat, bh);
    }

    @Benchmark
    public void concatSimple(BenchmarkState state, Blackhole bh) {
        concat(state, state.simpleConcat, bh);
    }

    @Benchmark
    public void concatGroovy(BenchmarkState state, Blackhole bh) {
        concat(state, state.groovyConcat, bh);
    }

    @Benchmark
    public void concatJactl(BenchmarkState state, Blackhole bh) {
        concat(state, state.jactlConcat, bh);
    }

    @Benchmark
    public void concatJavaLanguage(BenchmarkState state, Blackhole bh) {
        concat(state, state.javaLanguageConcat, bh);
    }

    @Benchmark
    public void concatMvel(BenchmarkState state, Blackhole bh) {
        concat(state, state.mvelConcat, bh);
    }

    @Benchmark
    public void concatJs(BenchmarkState state, Blackhole bh) {
        concat(state, state.jsConcat, bh);
    }

    @Benchmark
    public void concatPython3(BenchmarkState state, Blackhole bh) {
        concat(state, state.python3Concat, bh);
    }

    @Benchmark
    public void concatQuickjs(BenchmarkState state, Blackhole bh) {
        concat(state, state.quickjsConcat, bh);
    }

    private static void concat(BenchmarkState state, Expression expression, Blackhole bh) {
        Object out = expression.evaluate(state.concatExchange, String.class);
        state.concatExchange.setProperty(RESULT, out);
        bh.consume(out);
    }

    // scenario 1b: arithmetic on the body

    @Benchmark
    public void arithmeticJavaExpression(BenchmarkState state, Blackhole bh) {
        bh.consume(state.javaArithmetic.evaluate(state.arithmeticExchange, Integer.class));
    }

    @Benchmark
    public void arithmeticSimple(BenchmarkState state, Blackhole bh) {
        bh.consume(state.simpleArithmetic.evaluate(state.arithmeticExchange, Integer.class));
    }

    @Benchmark
    public void arithmeticGroovy(BenchmarkState state, Blackhole bh) {
        bh.consume(state.groovyArithmetic.evaluate(state.arithmeticExchange, Integer.class));
    }

    @Benchmark
    public void arithmeticJactl(BenchmarkState state, Blackhole bh) {
        bh.consume(state.jactlArithmetic.evaluate(state.arithmeticExchange, Integer.class));
    }

    @Benchmark
    public void arithmeticJavaLanguage(BenchmarkState state, Blackhole bh) {
        bh.consume(state.javaLanguageArithmetic.evaluate(state.arithmeticExchange, Integer.class));
    }

    @Benchmark
    public void arithmeticMvel(BenchmarkState state, Blackhole bh) {
        bh.consume(state.mvelArithmetic.evaluate(state.arithmeticExchange, Integer.class));
    }

    @Benchmark
    public void arithmeticJs(BenchmarkState state, Blackhole bh) {
        bh.consume(state.jsArithmetic.evaluate(state.arithmeticExchange, Integer.class));
    }

    @Benchmark
    public void arithmeticPython3(BenchmarkState state, Blackhole bh) {
        bh.consume(state.python3Arithmetic.evaluate(state.arithmeticExchange, Integer.class));
    }

    @Benchmark
    public void arithmeticQuickjs(BenchmarkState state, Blackhole bh) {
        bh.consume(state.quickjsArithmetic.evaluate(state.arithmeticExchange, Integer.class));
    }

    // scenario 2: predicate on a header

    @Benchmark
    public void predicateJava(BenchmarkState state, Blackhole bh) {
        bh.consume(state.javaPredicate.matches(state.predicateExchange));
    }

    @Benchmark
    public void predicateSimple(BenchmarkState state, Blackhole bh) {
        bh.consume(state.simplePredicate.matches(state.predicateExchange));
    }

    @Benchmark
    public void predicateGroovy(BenchmarkState state, Blackhole bh) {
        bh.consume(state.groovyPredicate.matches(state.predicateExchange));
    }

    @Benchmark
    public void predicateJactl(BenchmarkState state, Blackhole bh) {
        bh.consume(state.jactlPredicate.matches(state.predicateExchange));
    }

    @Benchmark
    public void predicateJavaLanguage(BenchmarkState state, Blackhole bh) {
        bh.consume(state.javaLanguagePredicate.matches(state.predicateExchange));
    }

    @Benchmark
    public void predicateMvel(BenchmarkState state, Blackhole bh) {
        bh.consume(state.mvelPredicate.matches(state.predicateExchange));
    }

    @Benchmark
    public void predicateJs(BenchmarkState state, Blackhole bh) {
        bh.consume(state.jsPredicate.matches(state.predicateExchange));
    }

    @Benchmark
    public void predicatePython3(BenchmarkState state, Blackhole bh) {
        bh.consume(state.python3Predicate.matches(state.predicateExchange));
    }

    @Benchmark
    public void predicateQuickjs(BenchmarkState state, Blackhole bh) {
        bh.consume(state.quickjsPredicate.matches(state.predicateExchange));
    }
}

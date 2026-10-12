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

import groovy.lang.GroovyShell;
import groovy.transform.CompileStatic;
import org.apache.camel.CamelContext;
import org.apache.camel.CamelContextAware;
import org.apache.camel.Exchange;
import org.apache.camel.Expression;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.language.groovy.GroovyShellFactory;
import org.apache.camel.language.jactl.JactlLanguage;
import org.apache.camel.language.python3.Python3Language;
import org.apache.camel.spi.GroovyScriptCompiler;
import org.apache.camel.spi.Language;
import org.apache.camel.support.DefaultExchange;
import org.apache.camel.support.ExpressionAdapter;
import org.apache.camel.support.service.ServiceHelper;
import org.codehaus.groovy.control.CompilerConfiguration;
import org.codehaus.groovy.control.customizers.ASTTransformationCustomizer;
import org.codehaus.groovy.control.customizers.ImportCustomizer;
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
 * Scenario 3: collection logic ("any line item above 100") over 10 / 1000 items, in Java, groovy (dynamic, static,
 * pre-compiled), jactl, java (jOOR), mvel, js (GraalJS), python3 (GraalPy) and quickjs (QuickJS4J).
 * <p>
 * jactl and python3 cannot call methods on a Java object by default (sandbox), so they use a language created with
 * {@code createWithHostAccess()}, bound in the registry of a separate CamelContext. quickjs never sees the Java object:
 * the body is serialized with Jackson into a JSON snapshot ({@code body.lineItems[].value}) for every evaluation.
 */
public class GroovyCollectionTest {

    static final String DYNAMIC_SCRIPT = "body.lineItems.any { it.value > 100 }";
    // the binding variable must be cast for static compilation, the logic is the same
    static final String STATIC_SCRIPT = "Order order = (Order) binding.getVariable('body')\n"
                                        + "order.lineItems.any { LineItem li -> li.value > 100 }";

    @Test
    public void launchBenchmark() throws Exception {
        new Runner(GroovyBenchmarkSupport.options(getClass(), "thrpt").build()).run();
    }

    @State(Scope.Thread)
    public static class BenchmarkState {
        @Param({ "10", "1000" })
        int size;

        CamelContext camel;
        CamelContext staticCamel;
        CamelContext hostAccessCamel;
        Exchange exchange;
        Exchange staticExchange;
        Exchange hostAccessExchange;

        Expression javaStreams;
        Expression groovyDynamic;
        Expression groovyCompileStatic;
        Expression precompiledDynamicDirect;
        Expression precompiledStaticDirect;
        Expression precompiledDynamicBean;
        Expression precompiledStaticBean;
        Expression jactlHostAccess;
        Expression javaLanguage;
        Expression mvel;
        Expression js;
        Expression python3HostAccess;
        Expression quickjs;

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            camel = new DefaultCamelContext();
            // same wiring as camel-main does for camel.main.groovyScriptPattern
            GroovyScriptCompiler compiler = camel.getCamelContextExtension().getContextPlugin(GroovyScriptCompiler.class);
            CamelContextAware.trySetCamelContext(compiler, camel);
            compiler.setScriptPattern("classpath:camel-groovy/*");
            camel.addService(compiler);
            ServiceHelper.startService(compiler);
            camel.start();

            OrderPredicate dynamicRules = (OrderPredicate) camel.getClassResolver().resolveMandatoryClass("OrderRules")
                    .getDeclaredConstructor().newInstance();
            OrderPredicate staticRules = (OrderPredicate) camel.getClassResolver().resolveMandatoryClass("OrderRulesStatic")
                    .getDeclaredConstructor().newInstance();

            // a GroovyShellFactory applies to every groovy expression of a context, so static compilation gets its own context
            staticCamel = new DefaultCamelContext();
            CompilerConfiguration cc = new CompilerConfiguration();
            cc.addCompilationCustomizers(
                    new ImportCustomizer().addImports(Order.class.getName(), LineItem.class.getName()),
                    new ASTTransformationCustomizer(CompileStatic.class));
            staticCamel.getRegistry().bind("staticShellFactory",
                    (GroovyShellFactory) e -> new GroovyShell(GroovyCollectionTest.class.getClassLoader(), cc));
            staticCamel.start();

            hostAccessCamel = new DefaultCamelContext();
            hostAccessCamel.getRegistry().bind("jactl", JactlLanguage.createWithHostAccess());
            hostAccessCamel.getRegistry().bind("python3", Python3Language.createWithHostAccess());
            hostAccessCamel.start();

            javaStreams = new ExpressionAdapter() {
                @Override
                public Object evaluate(Exchange e) {
                    return e.getMessage().getBody(Order.class).getLineItems().stream().anyMatch(i -> i.getValue() > 100);
                }
            };
            groovyDynamic = camel.resolveLanguage("groovy").createExpression(DYNAMIC_SCRIPT);
            groovyCompileStatic = staticCamel.resolveLanguage("groovy").createExpression(STATIC_SCRIPT);
            precompiledDynamicDirect = new ExpressionAdapter() {
                @Override
                public Object evaluate(Exchange e) {
                    return dynamicRules.anyAbove(e.getMessage().getBody(Order.class));
                }
            };
            precompiledStaticDirect = new ExpressionAdapter() {
                @Override
                public Object evaluate(Exchange e) {
                    return staticRules.anyAbove(e.getMessage().getBody(Order.class));
                }
            };
            Language bean = camel.resolveLanguage("bean");
            // properties: resultType, bean, method, beanType, ref, scope, validate
            precompiledDynamicBean = bean.createExpression(null,
                    new Object[] { Boolean.class, dynamicRules, "anyAbove", null, null, null, null });
            precompiledStaticBean = bean.createExpression(null,
                    new Object[] { Boolean.class, staticRules, "anyAbove", null, null, null, null });
            jactlHostAccess = hostAccessCamel.resolveLanguage("jactl")
                    .createExpression("body.getLineItems().anyMatch{ it.getValue() > 100 }");
            javaLanguage = camel.resolveLanguage("java").createExpression(
                    "bodyAs(org.apache.camel.itest.jmh.groovy.Order).getLineItems().stream().anyMatch(i -> i.getValue() > 100)");
            mvel = camel.resolveLanguage("mvel").createExpression("($ in request.body.lineItems if $.value > 100).size() > 0");
            js = camel.resolveLanguage("js").createExpression("body.getLineItems().stream().anyMatch(i => i.getValue() > 100)");
            python3HostAccess = hostAccessCamel.resolveLanguage("python3")
                    .createExpression("any(i.getValue() > 100 for i in body.getLineItems())");
            quickjs = camel.resolveLanguage("quickjs").createExpression("body.lineItems.some(i => i.value > 100)");

            for (Expression e : new Expression[] {
                    javaStreams, groovyDynamic, precompiledDynamicDirect, precompiledStaticDirect, javaLanguage, mvel, js,
                    quickjs }) {
                e.init(camel);
            }
            groovyCompileStatic.init(staticCamel);
            jactlHostAccess.init(hostAccessCamel);
            python3HostAccess.init(hostAccessCamel);

            for (boolean match : new boolean[] { false, true }) {
                exchange = new DefaultExchange(camel);
                exchange.getIn().setBody(Order.create(size, match));
                staticExchange = new DefaultExchange(staticCamel);
                staticExchange.getIn().setBody(exchange.getIn().getBody());
                hostAccessExchange = new DefaultExchange(hostAccessCamel);
                hostAccessExchange.getIn().setBody(exchange.getIn().getBody());
                check("javaStreams", match, javaStreams.evaluate(exchange, Boolean.class));
                check("groovyDynamic", match, groovyDynamic.evaluate(exchange, Boolean.class));
                check("groovyCompileStatic", match, groovyCompileStatic.evaluate(staticExchange, Boolean.class));
                check("precompiledDynamicDirect", match, precompiledDynamicDirect.evaluate(exchange, Boolean.class));
                check("precompiledStaticDirect", match, precompiledStaticDirect.evaluate(exchange, Boolean.class));
                check("precompiledDynamicBean", match, precompiledDynamicBean.evaluate(exchange, Boolean.class));
                check("precompiledStaticBean", match, precompiledStaticBean.evaluate(exchange, Boolean.class));
                check("jactlHostAccess", match, jactlHostAccess.evaluate(hostAccessExchange, Boolean.class));
                check("javaLanguage", match, javaLanguage.evaluate(exchange, Boolean.class));
                check("mvel", match, mvel.evaluate(exchange, Boolean.class));
                check("js", match, js.evaluate(exchange, Boolean.class));
                check("python3HostAccess", match, python3HostAccess.evaluate(hostAccessExchange, Boolean.class));
                check("quickjs", match, quickjs.evaluate(exchange, Boolean.class));
            }
        }

        @TearDown(Level.Trial)
        public void close() {
            hostAccessCamel.stop();
            staticCamel.stop();
            camel.stop();
        }
    }

    @Benchmark
    public void javaStreams(BenchmarkState state, Blackhole bh) {
        bh.consume(state.javaStreams.evaluate(state.exchange, Boolean.class));
    }

    @Benchmark
    public void groovyDynamic(BenchmarkState state, Blackhole bh) {
        bh.consume(state.groovyDynamic.evaluate(state.exchange, Boolean.class));
    }

    @Benchmark
    public void groovyCompileStatic(BenchmarkState state, Blackhole bh) {
        bh.consume(state.groovyCompileStatic.evaluate(state.staticExchange, Boolean.class));
    }

    @Benchmark
    public void precompiledDynamicDirect(BenchmarkState state, Blackhole bh) {
        bh.consume(state.precompiledDynamicDirect.evaluate(state.exchange, Boolean.class));
    }

    @Benchmark
    public void precompiledStaticDirect(BenchmarkState state, Blackhole bh) {
        bh.consume(state.precompiledStaticDirect.evaluate(state.exchange, Boolean.class));
    }

    @Benchmark
    public void precompiledDynamicBean(BenchmarkState state, Blackhole bh) {
        bh.consume(state.precompiledDynamicBean.evaluate(state.exchange, Boolean.class));
    }

    @Benchmark
    public void precompiledStaticBean(BenchmarkState state, Blackhole bh) {
        bh.consume(state.precompiledStaticBean.evaluate(state.exchange, Boolean.class));
    }

    @Benchmark
    public void jactlHostAccess(BenchmarkState state, Blackhole bh) {
        bh.consume(state.jactlHostAccess.evaluate(state.hostAccessExchange, Boolean.class));
    }

    @Benchmark
    public void javaLanguage(BenchmarkState state, Blackhole bh) {
        bh.consume(state.javaLanguage.evaluate(state.exchange, Boolean.class));
    }

    @Benchmark
    public void mvel(BenchmarkState state, Blackhole bh) {
        bh.consume(state.mvel.evaluate(state.exchange, Boolean.class));
    }

    @Benchmark
    public void js(BenchmarkState state, Blackhole bh) {
        bh.consume(state.js.evaluate(state.exchange, Boolean.class));
    }

    @Benchmark
    public void python3HostAccess(BenchmarkState state, Blackhole bh) {
        bh.consume(state.python3HostAccess.evaluate(state.hostAccessExchange, Boolean.class));
    }

    @Benchmark
    public void quickjs(BenchmarkState state, Blackhole bh) {
        bh.consume(state.quickjs.evaluate(state.exchange, Boolean.class));
    }
}

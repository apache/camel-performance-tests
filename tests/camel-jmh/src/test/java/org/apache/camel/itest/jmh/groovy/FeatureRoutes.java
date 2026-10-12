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

import java.util.List;

import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.builder.RouteBuilder;
import org.apache.camel.language.jactl.JactlLanguage;
import org.apache.camel.model.ProcessorDefinition;
import org.apache.camel.language.python3.Python3Language;
import org.apache.camel.language.quickjs.QuickjsLanguage;
import org.apache.camel.support.ExpressionAdapter;

/**
 * One route per scripting language that exercises every feature camel-quickjs offers, with the same logic in each
 * language: read headers, exchange variables and the exception binding (filter), a collection operation over the POJO
 * body (vip header), then set an exchange property (a sum over the body), an exchange variable (the exchange id) and a
 * header, log at debug level, and build the body from headers and an exchange property.
 * <p>
 * groovy, js (GraalJS), quickjs, jactl and mvel do the mutations inside one script. The two Python languages cannot
 * return a value from a multi-statement script, so their mutations are separate DSL steps. mvel has no closures, so its
 * sum calls the static {@link #sum(List)} helper. simple is not included: it has no collection operations.
 */
public final class FeatureRoutes {

    public static final List<String> LANGUAGES = List.of("java", "groovy", "js", "quickjs", "jactl", "mvel", "python3",
            "python");

    private FeatureRoutes() {
    }

    /** Called by the mvel script: MVEL has no closures to sum a projection with. */
    public static int sum(List<Integer> values) {
        int total = 0;
        for (Integer v : values) {
            total += v;
        }
        return total;
    }

    /** Registry bindings a language needs before the context starts (host access to call the POJO getters). */
    public static void configure(CamelContext camel, String language) {
        switch (language) {
            case "jactl" -> camel.getRegistry().bind("jactl",
                    JactlLanguage.createWithHostAccess().withAllowContextMapAll(true));
            case "python3" -> camel.getRegistry().bind("python3", Python3Language.createWithHostAccess());
            case "quickjs" -> {
                // -Dquickjs.maxEvaluations=N recycles engines by count (the native javy plugin has no observable memory)
                Integer max = Integer.getInteger("quickjs.maxEvaluations");
                if (max != null) {
                    QuickjsLanguage quickjs = new QuickjsLanguage();
                    quickjs.setEngineMaxEvaluations(max);
                    camel.getRegistry().bind("quickjs", quickjs);
                }
            }
            default -> {
            }
        }
    }

    public static RouteBuilder route(String language, Runnable onProcessed) {
        return new RouteBuilder() {
            @Override
            public void configure() {
                var r = from("direct:load").routeId("load")
                        .setVariable("enabled", constant(true))
                        .setProperty("batch", constant("b1"));
                ProcessorDefinition<?> tail = switch (language) {
                    case "java" -> r
                            .filter(e -> e.getMessage().getHeader("amount", Integer.class) > 100
                                    && Boolean.TRUE.equals(e.getVariable("enabled")) && e.getException() == null)
                            .setHeader("vip", new ExpressionAdapter() {
                                @Override
                                public Object evaluate(Exchange e) {
                                    return e.getMessage().getBody(Order.class).getLineItems().stream()
                                            .anyMatch(i -> i.getValue() > 90);
                                }
                            })
                            .setBody(new ExpressionAdapter() {
                                @Override
                                public Object evaluate(Exchange e) {
                                    Order order = e.getMessage().getBody(Order.class);
                                    e.setProperty("total",
                                            order.getLineItems().stream().mapToInt(LineItem::getValue).sum());
                                    e.setVariable("lastId", e.getExchangeId());
                                    e.getMessage().setHeader("processed", true);
                                    return "order-" + e.getMessage().getHeader("amount") + "-"
                                           + e.getMessage().getHeader("vip") + "-" + e.getProperty("batch");
                                }
                            });
                    case "groovy" -> r
                            .filter().groovy("headers.amount > 100 && variables.enabled && exception == null")
                            .setHeader("vip").groovy("body.lineItems.any { it.value > 90 }")
                            .setBody().groovy("exchange.setProperty('total', body.lineItems.sum { it.value })\n"
                                              + "exchange.setVariable('lastId', exchange.exchangeId)\n"
                                              + "exchange.in.setHeader('processed', true)\n"
                                              + "log.debug('processed')\n"
                                              + "'order-' + headers.amount + '-' + headers.vip + '-' + exchangeProperties.batch");
                    case "js" -> r
                            .filter().language("js", "headers.get('amount') > 100 && exchange.getVariable('enabled') === true"
                                                     + " && exchange.getException() === null")
                            .setHeader("vip").language("js",
                                    "body.getLineItems().stream().anyMatch(i => i.getValue() > 90)")
                            .setBody().language("js",
                                    "exchange.setProperty('total', body.getLineItems().stream().mapToInt(i => i.getValue()).sum());"
                                                + " exchange.setVariable('lastId', exchangeId);"
                                                + " message.setHeader('processed', true);"
                                                + " 'order-' + headers.get('amount') + '-' + headers.get('vip') + '-' + properties.get('batch')");
                    case "quickjs" -> r
                            .filter().language("quickjs",
                                    "headers.amount > 100 && variables.enabled === true && exception === null")
                            .setHeader("vip").language("quickjs", "body.lineItems.some(i => i.value > 90)")
                            .setBody().language("quickjs",
                                    "camel.setProperty('total', body.lineItems.reduce((a, i) => a + i.value, 0));"
                                                     + " camel.setVariable('lastId', exchangeId);"
                                                     + " camel.setHeader('processed', true);"
                                                     + " camel.log('debug', 'processed');"
                                                     + " 'order-' + headers.amount + '-' + camel.getHeader('vip') + '-' + properties.batch");
                    case "jactl" -> r
                            .filter().language("jactl", "headers.amount > 100 && variables.enabled && exception == null")
                            .setHeader("vip").language("jactl", "body.getLineItems().anyMatch{ it.getValue() > 90 }")
                            .setBody().language("jactl",
                                    "exchange.setProperty('total', body.getLineItems().map{ it.getValue() }.sum());"
                                                   + " exchange.setVariable('lastId', exchange.getExchangeId());"
                                                   + " request.setHeader('processed', true);"
                                                   + " 'order-' + headers.amount + '-' + headers.vip + '-' + exchange.getProperty('batch')");
                    case "mvel" -> r
                            .filter().language("mvel", "headers.amount > 100 && exchange.getVariable('enabled') == true"
                                                       + " && exception == null")
                            .setHeader("vip").language("mvel", "($ in request.body.lineItems if $.value > 90).size() > 0")
                            .setBody().language("mvel",
                                    "exchange.setProperty('total', org.apache.camel.itest.jmh.groovy.FeatureRoutes.sum(($.value in request.body.lineItems)));"
                                                  + " exchange.setVariable('lastId', exchangeId);"
                                                  + " request.setHeader('processed', true);"
                                                  + " 'order-' + headers.amount + '-' + headers.vip + '-' + properties.batch");
                    case "python3" -> r
                            .filter().language("python3", "headers['amount'] > 100 and exchange.getVariable('enabled') == True"
                                                          + " and exchange.getException() is None")
                            .setHeader("vip").language("python3", "any(i.getValue() > 90 for i in body.getLineItems())")
                            .setProperty("total").language("python3", "sum(i.getValue() for i in body.getLineItems())")
                            .setVariable("lastId").language("python3", "exchangeId")
                            .setHeader("processed").language("python3", "True")
                            .setBody().language("python3",
                                    "'order-%s-%s-%s' % (headers['amount'], str(headers['vip']).lower(), properties['batch'])");
                    case "python" -> r
                            .filter().language("python", "headers['amount'] > 100 and exchange.getVariable('enabled') == True"
                                                         + " and exchange.getException() is None")
                            .setHeader("vip").language("python", "any(i.getValue() > 90 for i in body.getLineItems())")
                            .setProperty("total").language("python", "sum(i.getValue() for i in body.getLineItems())")
                            .setVariable("lastId").language("python", "exchangeId")
                            .setHeader("processed").language("python", "True")
                            .setBody().language("python",
                                    "'order-%s-%s-%s' % (headers['amount'], str(headers['vip']).lower(), properties['batch'])");
                    default -> throw new IllegalArgumentException("Unknown language " + language);
                };
                // inside the filter block, like every step above: only messages that passed are counted
                tail.process(e -> onProcessed.run());
            }
        };
    }

    /** The values a processed message must carry, whatever the language. */
    public static void assertProcessed(Exchange exchange, int amount, boolean vip, int total) {
        String body = exchange.getMessage().getBody(String.class);
        if (!("order-" + amount + "-" + vip + "-b1").equals(body)) {
            throw new AssertionError("body: " + body);
        }
        if (!String.valueOf(vip).equalsIgnoreCase(String.valueOf(exchange.getMessage().getHeader("vip")))) {
            throw new AssertionError("vip: " + exchange.getMessage().getHeader("vip"));
        }
        if (!"true".equalsIgnoreCase(String.valueOf(exchange.getMessage().getHeader("processed")))) {
            throw new AssertionError("processed: " + exchange.getMessage().getHeader("processed"));
        }
        if (Integer.parseInt(String.valueOf(exchange.getProperty("total"))) != total) {
            throw new AssertionError("total: " + exchange.getProperty("total"));
        }
        if (!exchange.getExchangeId().equals(String.valueOf(exchange.getVariable("lastId")))) {
            throw new AssertionError("lastId: " + exchange.getVariable("lastId"));
        }
    }
}

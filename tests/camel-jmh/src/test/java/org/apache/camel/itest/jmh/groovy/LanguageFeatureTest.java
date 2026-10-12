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

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.impl.DefaultCamelContext;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;

/**
 * Every feature of the {@link FeatureRoutes} route, in every language: the bindings (headers, variables, exception,
 * exchange id, exchange properties, the POJO body), a collection operation, and the writes (header, exchange property,
 * exchange variable, body).
 */
public class LanguageFeatureTest {

    @Test
    public void testEveryFeatureInEveryLanguage() throws Exception {
        List<String> failures = new ArrayList<>();
        for (String language : FeatureRoutes.LANGUAGES) {
            try {
                testEveryFeature(language);
            } catch (Throwable t) {
                failures.add(language + ": " + t);
            }
        }
        assertEquals(List.of(), failures);
    }

    private void testEveryFeature(String language) throws Exception {
        CamelContext camel = new DefaultCamelContext();
        FeatureRoutes.configure(camel, language);
        AtomicInteger processed = new AtomicInteger();
        camel.addRoutes(FeatureRoutes.route(language, processed::incrementAndGet));
        camel.start();
        try {
            ProducerTemplate template = camel.createProducerTemplate();
            Order match = Order.create(20, true);
            Order noMatch = Order.create(20, false);
            int total = match.getLineItems().stream().mapToInt(LineItem::getValue).sum();

            Exchange out = template.request("direct:load", e -> {
                e.getMessage().setBody(match);
                e.getMessage().setHeaders(Map.of("amount", 150));
            });
            FeatureRoutes.assertProcessed(out, 150, true, total);

            out = template.request("direct:load", e -> {
                e.getMessage().setBody(noMatch);
                e.getMessage().setHeaders(Map.of("amount", 150));
            });
            FeatureRoutes.assertProcessed(out, 150, false,
                    noMatch.getLineItems().stream().mapToInt(LineItem::getValue).sum());

            // the filter drops a message below the amount, nothing after it runs
            out = template.request("direct:load", e -> {
                e.getMessage().setBody(match);
                e.getMessage().setHeaders(Map.of("amount", 50));
            });
            assertSame(match, out.getMessage().getBody());
            assertEquals(null, out.getMessage().getHeader("vip"));
            assertEquals(2, processed.get());
        } finally {
            camel.stop();
        }
    }
}

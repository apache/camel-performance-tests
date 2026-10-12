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

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Generates the JSON / XML / Map payloads for the data format benchmarks.
 */
public final class GroovyPayloads {

    private GroovyPayloads() {
    }

    public static int targetBytes(String payload) {
        return switch (payload) {
            case "1KB" -> 1024;
            case "1MB" -> 1024 * 1024;
            default -> throw new IllegalArgumentException(payload);
        };
    }

    public static int orders(String payload) {
        // one order is about 250 bytes of JSON
        return Math.max(1, targetBytes(payload) / 250);
    }

    public static byte[] json(int orders) {
        StringBuilder sb = new StringBuilder("{\"orders\":[");
        for (int i = 0; i < orders; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append("{\"id\":").append(i)
                    .append(",\"customer\":\"Customer ").append(i).append('"')
                    .append(",\"total\":").append(i).append(".5")
                    .append(",\"active\":").append(i % 2 == 0)
                    .append(",\"items\":[");
            for (int j = 0; j < 2; j++) {
                if (j > 0) {
                    sb.append(',');
                }
                sb.append("{\"sku\":\"SKU-").append(i).append('-').append(j).append('"')
                        .append(",\"qty\":").append(j + 1)
                        .append(",\"price\":").append(9 + j).append(".99}");
            }
            sb.append("]}");
        }
        sb.append("]}");
        return sb.toString().getBytes(StandardCharsets.UTF_8);
    }

    public static byte[] xml(int orders) {
        StringBuilder sb = new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<orders>");
        for (int i = 0; i < orders; i++) {
            sb.append("<order id=\"").append(i).append("\">")
                    .append("<customer>Customer ").append(i).append("</customer>")
                    .append("<total>").append(i).append(".5</total>")
                    .append("<active>").append(i % 2 == 0).append("</active>");
            for (int j = 0; j < 2; j++) {
                sb.append("<item sku=\"SKU-").append(i).append('-').append(j).append("\">")
                        .append("<qty>").append(j + 1).append("</qty>")
                        .append("<price>").append(9 + j).append(".99</price>")
                        .append("</item>");
            }
            sb.append("</order>");
        }
        sb.append("</orders>");
        return sb.toString().getBytes(StandardCharsets.UTF_8);
    }

    /**
     * The same orders as a Map in the shape groovyXml marshals: one root key, "_" prefixed keys become attributes and a
     * List becomes repeated elements.
     */
    public static Map<String, Object> xmlMap(int orders) {
        List<Map<String, Object>> list = new ArrayList<>(orders);
        for (int i = 0; i < orders; i++) {
            Map<String, Object> order = new LinkedHashMap<>();
            order.put("_id", i);
            order.put("customer", "Customer " + i);
            order.put("total", i + ".5");
            order.put("active", i % 2 == 0);
            List<Map<String, Object>> items = new ArrayList<>(2);
            for (int j = 0; j < 2; j++) {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("_sku", "SKU-" + i + "-" + j);
                item.put("qty", j + 1);
                item.put("price", (9 + j) + ".99");
                items.add(item);
            }
            order.put("item", items);
            list.add(order);
        }
        Map<String, Object> inner = new LinkedHashMap<>();
        inner.put("order", list);
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("orders", inner);
        return root;
    }
}

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

public class Order {

    private final List<LineItem> lineItems;

    public Order(List<LineItem> lineItems) {
        this.lineItems = lineItems;
    }

    public List<LineItem> getLineItems() {
        return lineItems;
    }

    /**
     * Creates an order where only the last line item is above 100 (when match is true), so an "any" scan has to visit
     * every item.
     */
    public static Order create(int size, boolean match) {
        List<LineItem> items = new ArrayList<>(size);
        for (int i = 0; i < size - 1; i++) {
            items.add(new LineItem("SKU-" + i, i % 100));
        }
        items.add(new LineItem("SKU-" + (size - 1), match ? 500 : 7));
        return new Order(items);
    }
}

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
package org.apache.camel.example;

import org.apache.camel.builder.RouteBuilder;

public class MyRouteBuilder extends RouteBuilder {

    @Override
    public void configure() throws Exception {
        from("timer:foo?delay=10s&period={{myPeriod}}&includeMetadata=false")
            // we can include a request body
            .setBody(constant("Hi from Camel"))
            .to("http://localhost:5678/")
            // the bigger the route the more object allocations
            // so lets test with 10 more steps
            .to("log:out0?level=OFF")
            .to("log:out1?level=OFF")
            .to("log:out2?level=OFF")
            .to("log:out3?level=OFF")
            .to("log:out4?level=OFF")
            .to("log:out5?level=OFF")
            .to("log:out6?level=OFF")
            .to("log:out7?level=OFF")
            .to("log:out8?level=OFF")
            .to("log:out9?level=OFF");
    }
}

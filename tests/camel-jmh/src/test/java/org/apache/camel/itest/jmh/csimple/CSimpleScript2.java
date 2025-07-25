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
package org.apache.camel.itest.jmh.csimple;

import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.Message;
import org.apache.camel.language.csimple.CSimpleSupport;

import static org.apache.camel.language.csimple.CSimpleHelper.headerAs;

public class CSimpleScript2 extends CSimpleSupport {

    public CSimpleScript2() {
    }

    @Override
    public String getText() {
        return "${header.gold} > 123";
    }

    @Override
    public Object evaluate(CamelContext context, Exchange exchange, Message message, Object body)
            throws Exception {
        return headerAs(message, "gold", int.class) > 123;
    }

    @Override
    public boolean isPredicate() {
        return true;
    }

}

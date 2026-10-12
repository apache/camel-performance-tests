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
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

import groovy.lang.Binding;
import groovy.lang.GroovyShell;
import groovy.lang.MissingPropertyException;
import groovy.lang.Script;
import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.Message;
import org.apache.camel.RuntimeCamelException;
import org.apache.camel.attachment.DefaultAttachmentMessage;
import org.apache.camel.language.groovy.GroovyExpression;
import org.apache.camel.language.groovy.GroovyShellFactory;
import org.apache.camel.support.ExchangeHelper;
import org.apache.camel.support.ExpressionSupport;
import org.apache.camel.support.LanguageHelper;
import org.apache.camel.trait.message.MessageTrait;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Benchmark-only prototype of a cheaper GroovyExpression. It keeps the same script semantics (a new Script instance per
 * evaluation, so it stays thread safe) but:
 * <ul>
 * <li>looks up the GroovyShellFactory once per CamelContext instead of per evaluation</li>
 * <li>keeps the compiled class on the expression, so a cache hit needs no language lookup and no key concatenation</li>
 * <li>creates the Script through a MethodHandle instead of reflection</li>
 * <li>builds a single pre-sized variables map, and only wraps the message for attachments when it has any</li>
 * <li>optionally uses a lazy binding that resolves exchange variables only when the script reads them</li>
 * </ul>
 * It does not implement dev-mode reload (clearing the cached class), which a real change must keep.
 */
public class OptimizedGroovyExpression extends ExpressionSupport {

    private static final Logger LOG = LoggerFactory.getLogger(GroovyExpression.class);
    private static final MethodType SCRIPT_CONSTRUCTOR = MethodType.methodType(void.class);

    private final String text;
    private final boolean lazyBinding;

    private volatile CamelContext context;
    private volatile GroovyShellFactory shellFactory;
    private volatile String compiledFileName;
    private volatile MethodHandle constructor;

    public OptimizedGroovyExpression(String text, boolean lazyBinding) {
        this.text = text;
        this.lazyBinding = lazyBinding;
    }

    @Override
    protected String assertionFailureMessage(Exchange exchange) {
        return "groovy: " + text;
    }

    @Override
    public <T> T evaluate(Exchange exchange, Class<T> type) {
        CamelContext camelContext = exchange.getContext();
        if (context != camelContext) {
            Set<GroovyShellFactory> factories = camelContext.getRegistry().findByType(GroovyShellFactory.class);
            shellFactory = factories.size() == 1 ? factories.iterator().next() : null;
            constructor = null;
            context = camelContext;
        }
        GroovyShellFactory factory = shellFactory;
        Map<String, Object> globals = Collections.emptyMap();
        String fileName = null;
        if (factory != null) {
            fileName = factory.getFileName(exchange);
            globals = factory.getVariables(exchange);
        }

        MethodHandle ctor = constructor;
        if (ctor == null || (fileName != null && !fileName.equals(compiledFileName))) {
            ctor = compile(exchange, factory, fileName);
        }
        Script script;
        try {
            script = (Script) ctor.invokeExact();
        } catch (Throwable e) {
            throw RuntimeCamelException.wrapRuntimeCamelException(e);
        }
        script.setBinding(lazyBinding ? new ExchangeBinding(exchange, globals) : eagerBinding(exchange, globals));
        return camelContext.getTypeConverter().convertTo(type, script.run());
    }

    @SuppressWarnings("unchecked")
    private synchronized MethodHandle compile(Exchange exchange, GroovyShellFactory factory, String fileName) {
        GroovyShell shell = factory != null ? factory.createGroovyShell(exchange) : new GroovyShell();
        Class<Script> clazz = fileName != null
                ? shell.getClassLoader().parseClass(text, fileName) : shell.getClassLoader().parseClass(text);
        try {
            MethodHandle ctor = MethodHandles.publicLookup().findConstructor(clazz, SCRIPT_CONSTRUCTOR)
                    .asType(MethodType.methodType(Script.class));
            compiledFileName = fileName;
            constructor = ctor;
            return ctor;
        } catch (ReflectiveOperationException e) {
            throw new RuntimeCamelException(e);
        }
    }

    private static Binding eagerBinding(Exchange exchange, Map<String, Object> globals) {
        Map<String, Object> map = new HashMap<>(32);
        if (!globals.isEmpty()) {
            map.putAll(globals);
        }
        ExchangeHelper.populateVariableMap(exchange, map, true);
        map.put("attachments", attachments(exchange.getMessage()));
        map.put("log", LOG);
        return new Binding(map);
    }

    private static Map<?, ?> attachments(Message message) {
        if (message.hasTrait(MessageTrait.ATTACHMENTS)) {
            DefaultAttachmentMessage am = new DefaultAttachmentMessage(message);
            if (am.hasAttachments()) {
                return am.getAttachments();
            }
        }
        return Collections.emptyMap();
    }

    /**
     * Resolves the well known variables from the exchange when the script reads them. Note the semantic difference: the
     * values are read at access time, not when the binding is created.
     */
    static final class ExchangeBinding extends Binding {
        private final Exchange exchange;
        private final Map<String, Object> globals;

        ExchangeBinding(Exchange exchange, Map<String, Object> globals) {
            this.exchange = exchange;
            this.globals = globals;
        }

        @Override
        public Object getVariable(String name) {
            Map<?, ?> local = super.getVariables();
            if (!local.isEmpty() && local.containsKey(name)) {
                return local.get(name);
            }
            switch (name) {
                case "body":
                    return exchange.getIn().getBody();
                case "header":
                case "headers":
                    return exchange.getIn().getHeaders();
                case "variable":
                case "variables":
                    return exchange.getVariables();
                case "exception":
                    return LanguageHelper.exception(exchange);
                case "in":
                case "request":
                    return exchange.getIn();
                case "exchange":
                    return exchange;
                case "exchangeProperty":
                case "exchangeProperties":
                    return exchange.getAllProperties();
                case "out":
                case "response":
                    if (exchange.getPattern().isOutCapable()) {
                        return exchange.getMessage();
                    }
                    break;
                case "camelContext":
                    return exchange.getContext();
                case "attachments":
                    return attachments(exchange.getMessage());
                case "log":
                    return LOG;
                default:
                    break;
            }
            if (globals.containsKey(name)) {
                return globals.get(name);
            }
            throw new MissingPropertyException(name, getClass());
        }

        @Override
        public boolean hasVariable(String name) {
            try {
                getVariable(name);
                return true;
            } catch (MissingPropertyException e) {
                return false;
            }
        }
    }
}

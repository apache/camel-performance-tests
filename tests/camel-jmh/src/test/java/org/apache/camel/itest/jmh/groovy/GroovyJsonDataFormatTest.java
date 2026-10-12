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

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.util.Map;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import groovy.json.JsonOutput;
import groovy.json.JsonParserType;
import groovy.json.JsonSlurper;
import groovy.json.StreamingJsonBuilder;
import org.apache.camel.CamelContext;
import org.apache.camel.CamelContextAware;
import org.apache.camel.Exchange;
import org.apache.camel.component.jackson.JacksonDataFormat;
import org.apache.camel.groovy.json.GroovyJSonlDataFormat;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.spi.DataFormat;
import org.apache.camel.support.DefaultExchange;
import org.apache.camel.support.service.ServiceHelper;
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
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import static org.apache.camel.itest.jmh.groovy.GroovyBenchmarkSupport.check;
import static org.apache.camel.itest.jmh.groovy.GroovyBenchmarkSupport.walk;

/**
 * Scenario 7 (JSON): groovyJson vs Jackson marshal/unmarshal with 1 KB and 1 MB payloads.
 */
public class GroovyJsonDataFormatTest {

    private static final Logger LOG = LoggerFactory.getLogger(GroovyJsonDataFormatTest.class);

    @Test
    public void launchBenchmark() throws Exception {
        new Runner(GroovyBenchmarkSupport.options(getClass(), "avgt").build()).run();
    }

    @State(Scope.Thread)
    public static class BenchmarkState {
        @Param({ "1KB", "1MB" })
        String payload;

        CamelContext camel;
        Exchange exchange;
        byte[] json;
        Map<String, Object> map;

        GroovyJSonlDataFormat groovyPretty;
        GroovyJSonlDataFormat groovyCompact;
        JacksonDataFormat jacksonCompact;
        JacksonDataFormat jacksonPretty;

        @Setup(Level.Trial)
        @SuppressWarnings("unchecked")
        public void initialize() throws Exception {
            camel = new DefaultCamelContext();
            camel.start();
            exchange = new DefaultExchange(camel);
            json = GroovyPayloads.json(GroovyPayloads.orders(payload));

            groovyPretty = new GroovyJSonlDataFormat();
            groovyCompact = new GroovyJSonlDataFormat();
            groovyCompact.setPrettyPrint(false);
            jacksonCompact = new JacksonDataFormat();
            jacksonPretty = new JacksonDataFormat();
            jacksonPretty.setPrettyPrint(true);
            for (Object df : new Object[] { groovyPretty, groovyCompact, jacksonCompact, jacksonPretty }) {
                CamelContextAware.trySetCamelContext(df, camel);
                ServiceHelper.startService(df);
            }
            map = (Map<String, Object>) jacksonCompact.unmarshal(exchange, new ByteArrayInputStream(json));

            // unmarshal: same tree
            long expected = walk(map);
            check("unmarshalGroovy", expected, walk(groovyPretty.unmarshal(exchange, new ByteArrayInputStream(json))));
            check("unmarshalGroovyIndexOverlay", expected,
                    walk(new JsonSlurper().setType(JsonParserType.INDEX_OVERLAY).parse(new ByteArrayInputStream(json))));

            // marshal: same JSON document
            ObjectMapper mapper = new ObjectMapper();
            JsonNode expectedTree = mapper.readTree(json);
            check("marshalGroovyPretty", expectedTree, mapper.readTree(marshal(groovyPretty, exchange, map)));
            check("marshalJsonOutputToJson", expectedTree, mapper.readTree(JsonOutput.toJson(map)));
            check("marshalGroovyStreaming", expectedTree, mapper.readTree(streaming(map)));
            check("marshalJacksonCompact", expectedTree, mapper.readTree(marshal(jacksonCompact, exchange, map)));
            check("marshalJacksonPretty", expectedTree, mapper.readTree(marshal(jacksonPretty, exchange, map)));
            JsonNode compact = mapper.readTree(marshal(groovyCompact, exchange, map));
            if (!expectedTree.equals(compact)) {
                // camel main: prettyPrint=false writes the JSON document as a quoted JSON string (fixed by CAMEL-24669)
                System.out.println("SETUP groovyJson prettyPrint=false does NOT produce the same document (node type "
                                   + compact.getNodeType() + "), marshalGroovyCompact is not equal work");
            }
        }

        @TearDown(Level.Trial)
        public void close() {
            camel.stop();
        }
    }

    static byte[] marshal(DataFormat df, Exchange exchange, Object graph) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        df.marshal(exchange, graph, bos);
        return bos.toByteArray();
    }

    static byte[] streaming(Map<String, Object> map) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        try (Writer writer = new OutputStreamWriter(bos, StandardCharsets.UTF_8)) {
            new StreamingJsonBuilder(writer).call(map);
        }
        return bos.toByteArray();
    }

    // unmarshal

    @Benchmark
    public void unmarshalGroovy(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(state.groovyPretty.unmarshal(state.exchange, new ByteArrayInputStream(state.json)));
    }

    @Benchmark
    public void unmarshalJackson(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(state.jacksonCompact.unmarshal(state.exchange, new ByteArrayInputStream(state.json)));
    }

    @Benchmark
    public void unmarshalWalkGroovy(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(walk(state.groovyPretty.unmarshal(state.exchange, new ByteArrayInputStream(state.json))));
    }

    @Benchmark
    public void unmarshalWalkGroovyIndexOverlay(BenchmarkState state, Blackhole bh) {
        JsonSlurper slurper = new JsonSlurper().setType(JsonParserType.INDEX_OVERLAY);
        bh.consume(walk(slurper.parse(new ByteArrayInputStream(state.json))));
    }

    @Benchmark
    public void unmarshalWalkJackson(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(walk(state.jacksonCompact.unmarshal(state.exchange, new ByteArrayInputStream(state.json))));
    }

    // marshal

    @Benchmark
    public void marshalGroovyPretty(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(marshal(state.groovyPretty, state.exchange, state.map));
    }

    /**
     * NOT equal work on camel main: prettyPrint=false double-encodes the document (see setup log).
     */
    @Benchmark
    public void marshalGroovyCompact(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(marshal(state.groovyCompact, state.exchange, state.map));
    }

    /**
     * What groovyJson prettyPrint=false does once CAMEL-24669 is merged: JsonOutput.toJson + String.getBytes.
     */
    @Benchmark
    public void marshalJsonOutputToJson(BenchmarkState state, Blackhole bh) {
        bh.consume(JsonOutput.toJson(state.map).getBytes());
    }

    /**
     * Candidate: StreamingJsonBuilder writes straight to the stream (no intermediate String).
     */
    @Benchmark
    public void marshalGroovyStreaming(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(streaming(state.map));
    }

    @Benchmark
    public void marshalJacksonCompact(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(marshal(state.jacksonCompact, state.exchange, state.map));
    }

    @Benchmark
    public void marshalJacksonPretty(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(marshal(state.jacksonPretty, state.exchange, state.map));
    }
}

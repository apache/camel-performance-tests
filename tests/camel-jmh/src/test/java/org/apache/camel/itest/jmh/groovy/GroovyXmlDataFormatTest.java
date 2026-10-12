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

import java.io.BufferedOutputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.util.Map;

import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.SAXParserFactory;
import javax.xml.stream.XMLInputFactory;
import javax.xml.stream.XMLStreamConstants;
import javax.xml.stream.XMLStreamReader;

import groovy.util.Node;
import groovy.xml.FactorySupport;
import groovy.xml.XmlParser;
import org.apache.camel.CamelContext;
import org.apache.camel.CamelContextAware;
import org.apache.camel.Exchange;
import org.apache.camel.component.jacksonxml.JacksonXMLDataFormat;
import org.apache.camel.groovy.xml.GroovyXmlDataFormat;
import org.apache.camel.impl.DefaultCamelContext;
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
import org.w3c.dom.Document;

import static org.apache.camel.itest.jmh.groovy.GroovyBenchmarkSupport.check;

/**
 * Scenario 7 (XML): groovyXml unmarshal vs JAXP DOM / StAX / jacksonXml, and Map to XML marshal, 1 KB and 1 MB.
 */
public class GroovyXmlDataFormatTest {

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
        byte[] xml;
        Map<String, Object> map;

        GroovyXmlDataFormat groovyXml;
        JacksonXMLDataFormat jacksonXml;
        SAXParserFactory saxFactory;
        DocumentBuilderFactory domFactory;
        XMLInputFactory staxFactory;
        OutputStream devNull;
        OutputStream bufferedDevNull;

        @Setup(Level.Trial)
        public void initialize() throws Exception {
            camel = new DefaultCamelContext();
            camel.start();
            exchange = new DefaultExchange(camel);
            int orders = GroovyPayloads.orders(payload);
            xml = GroovyPayloads.xml(orders);
            map = GroovyPayloads.xmlMap(orders);

            groovyXml = new GroovyXmlDataFormat();
            jacksonXml = new JacksonXMLDataFormat();
            for (Object df : new Object[] { groovyXml, jacksonXml }) {
                CamelContextAware.trySetCamelContext(df, camel);
                ServiceHelper.startService(df);
            }

            // same configuration as new XmlParser(), but the factory is created once
            saxFactory = FactorySupport.createSaxParserFactory();
            saxFactory.setNamespaceAware(true);
            saxFactory.setValidating(false);
            saxFactory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            saxFactory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);

            domFactory = DocumentBuilderFactory.newInstance();
            domFactory.setNamespaceAware(true);
            domFactory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            domFactory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);

            staxFactory = XMLInputFactory.newInstance();
            staxFactory.setProperty(XMLInputFactory.SUPPORT_DTD, false);
            staxFactory.setProperty(XMLInputFactory.IS_SUPPORTING_EXTERNAL_ENTITIES, false);

            // jackson closes the target stream, so the shared sinks must ignore close()
            devNull = new NonClosingOutputStream(new FileOutputStream("/dev/null"));
            bufferedDevNull = new NonClosingOutputStream(new BufferedOutputStream(new FileOutputStream("/dev/null")));

            // unmarshal: same number of elements
            int elements = domElements(xml);
            check("unmarshalGroovyXml", elements,
                    ((Node) groovyXml.unmarshal(exchange, new ByteArrayInputStream(xml))).depthFirst().size());
            check("unmarshalGroovyXmlCachedFactory", elements,
                    new XmlParser(saxFactory.newSAXParser()).parse(new ByteArrayInputStream(xml)).depthFirst().size());
            check("unmarshalStaxScan", (long) elements, staxScan(staxFactory, xml) >>> 32);
            check("unmarshalJacksonXml", true,
                    jacksonXml.unmarshal(exchange, new ByteArrayInputStream(xml)) instanceof Map);

            // marshal: both produce well-formed XML with a comparable number of elements
            ByteArrayOutputStream groovyOut = new ByteArrayOutputStream();
            groovyXml.marshal(exchange, map, groovyOut);
            ByteArrayOutputStream jacksonOut = new ByteArrayOutputStream();
            jacksonXml.marshal(exchange, map, jacksonOut);
            System.out.printf(
                    "SETUP payload=%s input=%d bytes/%d elements, marshal groovyXml=%d bytes/%d elements, jacksonXml=%d bytes/%d elements%n",
                    payload, xml.length, elements, groovyOut.size(), domElements(groovyOut.toByteArray()),
                    jacksonOut.size(), domElements(jacksonOut.toByteArray()));
        }

        int domElements(byte[] data) throws Exception {
            Document doc = domFactory.newDocumentBuilder().parse(new ByteArrayInputStream(data));
            return doc.getElementsByTagName("*").getLength();
        }

        @TearDown(Level.Trial)
        public void close() throws Exception {
            ((NonClosingOutputStream) devNull).delegate.close();
            ((NonClosingOutputStream) bufferedDevNull).delegate.close();
            camel.stop();
        }
    }

    static final class NonClosingOutputStream extends OutputStream {
        final OutputStream delegate;

        NonClosingOutputStream(OutputStream delegate) {
            this.delegate = delegate;
        }

        @Override
        public void write(int b) throws IOException {
            delegate.write(b);
        }

        @Override
        public void write(byte[] b, int off, int len) throws IOException {
            delegate.write(b, off, len);
        }

        @Override
        public void flush() throws IOException {
            delegate.flush();
        }

        @Override
        public void close() {
            // ignore
        }
    }

    /**
     * Reads every event and every text value; returns elements in the upper 32 bits and characters in the lower 32.
     */
    static long staxScan(XMLInputFactory factory, byte[] xml) throws Exception {
        XMLStreamReader reader = factory.createXMLStreamReader(new ByteArrayInputStream(xml));
        long elements = 0;
        long chars = 0;
        while (reader.hasNext()) {
            int event = reader.next();
            if (event == XMLStreamConstants.START_ELEMENT) {
                elements++;
                for (int i = 0; i < reader.getAttributeCount(); i++) {
                    chars += reader.getAttributeValue(i).length();
                }
            } else if (event == XMLStreamConstants.CHARACTERS) {
                chars += reader.getText().length();
            }
        }
        reader.close();
        return elements << 32 | chars;
    }

    // unmarshal

    @Benchmark
    public void unmarshalGroovyXml(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(state.groovyXml.unmarshal(state.exchange, new ByteArrayInputStream(state.xml)));
    }

    /**
     * Candidate: reuse a configured SAXParserFactory instead of creating one in every new XmlParser().
     */
    @Benchmark
    public void unmarshalGroovyXmlCachedFactory(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(new XmlParser(state.saxFactory.newSAXParser()).parse(new ByteArrayInputStream(state.xml)));
    }

    @Benchmark
    public void unmarshalDom(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(state.domFactory.newDocumentBuilder().parse(new ByteArrayInputStream(state.xml)));
    }

    /**
     * Not a tree: StAX scan of every event, the cheapest possible full read.
     */
    @Benchmark
    public void unmarshalStaxScan(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(staxScan(state.staxFactory, state.xml));
    }

    @Benchmark
    public void unmarshalJacksonXml(BenchmarkState state, Blackhole bh) throws Exception {
        bh.consume(state.jacksonXml.unmarshal(state.exchange, new ByteArrayInputStream(state.xml)));
    }

    // marshal a Map

    @Benchmark
    public void marshalMapGroovyXml(BenchmarkState state, Blackhole bh) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        state.groovyXml.marshal(state.exchange, state.map, bos);
        bh.consume(bos.toByteArray());
    }

    /**
     * Unbuffered file stream: every small os.write() of the serializer is a system call.
     */
    @Benchmark
    public void marshalMapGroovyXmlDevNull(BenchmarkState state) throws Exception {
        state.groovyXml.marshal(state.exchange, state.map, state.devNull);
    }

    @Benchmark
    public void marshalMapGroovyXmlBufferedDevNull(BenchmarkState state) throws Exception {
        state.groovyXml.marshal(state.exchange, state.map, state.bufferedDevNull);
        state.bufferedDevNull.flush();
    }

    @Benchmark
    public void marshalMapJacksonXml(BenchmarkState state, Blackhole bh) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        state.jacksonXml.marshal(state.exchange, state.map, bos);
        bh.consume(bos.toByteArray());
    }

    @Benchmark
    public void marshalMapJacksonXmlDevNull(BenchmarkState state) throws Exception {
        state.jacksonXml.marshal(state.exchange, state.map, state.devNull);
    }
}

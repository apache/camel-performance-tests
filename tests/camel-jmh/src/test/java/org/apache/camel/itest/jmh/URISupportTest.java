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

package org.apache.camel.itest.jmh;

import java.io.UnsupportedEncodingException;
import java.net.URISyntaxException;
import java.util.concurrent.TimeUnit;

import org.apache.camel.util.URISupport;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Warmup;
import org.openjdk.jmh.infra.Blackhole;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;

@State(Scope.Thread)
public class URISupportTest {

    private String simpleQueryPart = "?level=INFO&logMask=false&exchangeFormatter=#myFormatter";

    @Test
    public void launchBenchmark() throws Exception {
        Options opt = new OptionsBuilder()
                // Specify which benchmarks to run.
                // You can be more specific if you'd like to run only one benchmark per test.
                .include(this.getClass().getName() + ".*")
                .forks(1)
                .resultFormat(ResultFormatType.JSON)
                .result(this.getClass().getSimpleName() + ".jmh.json")
                .build();

        new Runner(opt).run();
    }

    // We may need to keep these here: we want to try to prevent constant-folding from kicking in!
    private String logUri = "log:foo?level=INFO&logMask=false&exchangeFormatter=#myFormatter";
    private String fastUriWithRaw = "xmpp://camel-user@localhost:123/test-user@localhost?password=RAW(++?w0rd)&serviceName=some chat";
    private String queryWithRawType1 = "?level=INFO&logMask=false&exchangeFormatter=#myFormatter&password=RAW(++?w0rd)";
    private String queryWithRawType2 = "?level=INFO&logMask=false&exchangeFormatter=#myFormatter&password=RAW{++?w0rd}";
    private String queryWithPercent = "?level=INFO&logMask=false&exchangeFormatter=#myFormatter&keyWithPercent=%valueWhatever";

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @Warmup(iterations = 10, batchSize = 5000)
    @Measurement(iterations = 20, batchSize = 50000)
    @BenchmarkMode(Mode.SingleShotTime)
    @Benchmark
    public void normalizeFastUri(Blackhole bh) throws UnsupportedEncodingException, URISyntaxException {
        bh.consume(URISupport.normalizeUri(logUri));
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @Warmup(iterations = 10, batchSize = 5000)
    @Measurement(iterations = 20, batchSize = 50000)
    @BenchmarkMode(Mode.SingleShotTime)
    @Benchmark
    public void normalizeFastUriWithRAW(Blackhole bh) throws UnsupportedEncodingException, URISyntaxException {
        bh.consume(URISupport.normalizeUri(fastUriWithRaw));
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @Warmup(iterations = 10, batchSize = 5000)
    @Measurement(iterations = 20, batchSize = 50000)
    @BenchmarkMode(Mode.SingleShotTime)
    @Benchmark
    public void parseQuery(Blackhole bh) throws URISyntaxException {
        bh.consume(URISupport.parseQuery(simpleQueryPart));
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @Warmup(iterations = 10, batchSize = 5000)
    @Measurement(iterations = 20, batchSize = 50000)
    @BenchmarkMode(Mode.SingleShotTime)
    @Benchmark
    public void parseQueryWithRAW1(Blackhole bh) throws URISyntaxException {
        bh.consume(URISupport.parseQuery(queryWithRawType1));
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @Warmup(iterations = 10, batchSize = 5000)
    @Measurement(iterations = 20, batchSize = 50000)
    @BenchmarkMode(Mode.SingleShotTime)
    @Benchmark
    public void parseQueryWithRAW2(Blackhole bh) throws URISyntaxException {
        bh.consume(URISupport.parseQuery(queryWithRawType2));
    }

    @OutputTimeUnit(TimeUnit.MICROSECONDS)
    @Warmup(iterations = 10, batchSize = 5000)
    @Measurement(iterations = 20, batchSize = 50000)
    @BenchmarkMode(Mode.SingleShotTime)
    @Benchmark
    public void parseQueryWithPercent(Blackhole bh) throws URISyntaxException {
        bh.consume(URISupport.parseQuery(queryWithPercent));
    }
}

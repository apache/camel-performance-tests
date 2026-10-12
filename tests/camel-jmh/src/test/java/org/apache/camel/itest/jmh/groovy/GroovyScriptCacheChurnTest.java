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

import java.io.File;
import java.lang.management.ClassLoadingMXBean;
import java.lang.ref.WeakReference;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryPoolMXBean;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import org.apache.camel.CamelContext;
import org.apache.camel.Exchange;
import org.apache.camel.Expression;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.spi.Language;
import org.apache.camel.support.DefaultExchange;
import org.junit.jupiter.api.Test;

/**
 * Scenario 5d: not a JMH benchmark but a deterministic harness that counts script (re)compilations, Metaspace and class
 * loading when the groovy script cache evicts, when threads miss the cache concurrently and when soft references are
 * cleared. Each script returns its own class, so a new class identity means the script was compiled again.
 * <p>
 * Run twice to compare soft reference policies:
 *
 * <pre>
 * mvn test -P jmh -Dtest=GroovyScriptCacheChurnTest
 * mvn test -P jmh -Dtest=GroovyScriptCacheChurnTest -DargLine=-XX:SoftRefLRUPolicyMSPerMB=0 -Djmh.suffix=-softref0
 * </pre>
 */
public class GroovyScriptCacheChurnTest {

    private final StringBuilder report = new StringBuilder();

    @Test
    public void launchBenchmark() throws Exception {
        line("java.vm.version=%s inputArguments=%s", System.getProperty("java.vm.version"),
                ManagementFactory.getRuntimeMXBean().getInputArguments());
        roundRobin(1000, 3);
        roundRobin(1001, 3);
        roundRobin(2000, 3);
        hotScriptEviction(1500);
        concurrentMiss(8, 50);
        softReferenceClearing(50, 3);

        String dir = System.getProperty("jmh.resultDir", ".");
        new File(dir).mkdirs();
        File out = new File(dir, "GroovyScriptCacheChurnTest" + System.getProperty("jmh.suffix", "") + ".txt");
        Files.writeString(out.toPath(), report.toString());
        System.out.println(report);
    }

    private void roundRobin(int distinct, int rounds) throws Exception {
        CamelContext camel = context();
        Exchange exchange = exchange(camel);
        Language groovy = camel.resolveLanguage("groovy");
        List<Expression> expressions = new ArrayList<>();
        for (int i = 0; i < distinct; i++) {
            expressions.add(groovy.createExpression("getClass() // rr-" + distinct + "-" + i));
        }
        // weak references only: the harness must not keep evicted script classes alive
        List<WeakReference<Class<?>>> lastClass = new ArrayList<>();
        for (Expression e : expressions) {
            lastClass.add(new WeakReference<>(e.evaluate(exchange, Class.class)));
        }
        long metaspaceBefore = metaspaceUsedAfterGc();
        ClassLoadingMXBean cl = ManagementFactory.getClassLoadingMXBean();
        long loadedBefore = cl.getTotalLoadedClassCount();
        long unloadedBefore = cl.getUnloadedClassCount();

        long recompilations = 0;
        long start = System.nanoTime();
        for (int r = 0; r < rounds; r++) {
            for (int i = 0; i < distinct; i++) {
                Class<?> c = expressions.get(i).evaluate(exchange, Class.class);
                if (lastClass.get(i).get() != c) {
                    recompilations++;
                    lastClass.set(i, new WeakReference<>(c));
                }
            }
        }
        long took = System.nanoTime() - start;
        long metaspaceBeforeGc = metaspaceUsed();
        long metaspaceAfter = metaspaceUsedAfterGc();
        long evaluations = (long) distinct * rounds;
        line("roundRobin distinct=%d rounds=%d evaluations=%d recompilations=%d avg=%.1f us/eval "
             + "classesLoaded=+%d classesUnloaded=+%d metaspace(MB) before=%.1f peak=%.1f afterGc=%.1f",
                distinct, rounds, evaluations, recompilations, took / 1000.0 / evaluations,
                cl.getTotalLoadedClassCount() - loadedBefore, cl.getUnloadedClassCount() - unloadedBefore,
                mb(metaspaceBefore), mb(metaspaceBeforeGc), mb(metaspaceAfter));
        camel.stop();
    }

    private void hotScriptEviction(int coldScripts) throws Exception {
        CamelContext camel = context();
        Exchange exchange = exchange(camel);
        Language groovy = camel.resolveLanguage("groovy");
        Expression hot = groovy.createExpression("getClass() // hot");
        Class<?> hotClass = hot.evaluate(exchange, Class.class);
        int firstRecompile = -1;
        int recompiles = 0;
        for (int i = 1; i <= coldScripts; i++) {
            groovy.createExpression("getClass() // cold-" + i).evaluate(exchange, Class.class);
            // the hot script is used after every cold one, so an LRU cache would never evict it
            Class<?> current = hot.evaluate(exchange, Class.class);
            if (current != hotClass) {
                recompiles++;
                if (firstRecompile < 0) {
                    firstRecompile = i;
                }
                hotClass = current;
            }
        }
        line("hotScriptEviction coldScripts=%d hotScriptEvaluations=%d hotScriptRecompilations=%d firstRecompilationAfterColdScript=%d",
                coldScripts, coldScripts, recompiles, firstRecompile);
        camel.stop();
    }

    private void concurrentMiss(int threads, int trials) throws Exception {
        CamelContext camel = context();
        Language groovy = camel.resolveLanguage("groovy");
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        int total = 0;
        int max = 0;
        for (int t = 0; t < trials; t++) {
            Expression expression = groovy.createExpression("getClass() // concurrent-" + t);
            CyclicBarrier barrier = new CyclicBarrier(threads);
            List<Future<Class<?>>> futures = new ArrayList<>();
            for (int i = 0; i < threads; i++) {
                futures.add(pool.submit(() -> {
                    Exchange exchange = exchange(camel);
                    barrier.await();
                    return expression.evaluate(exchange, Class.class);
                }));
            }
            Set<Class<?>> classes = identitySet();
            for (Future<Class<?>> f : futures) {
                classes.add(f.get());
            }
            total += classes.size();
            max = Math.max(max, classes.size());
        }
        pool.shutdown();
        line("concurrentMiss threads=%d trials=%d compilationsPerNewScript avg=%.2f max=%d (1 = no duplicate compilation)",
                threads, trials, (double) total / trials, max);
        camel.stop();
    }

    private void softReferenceClearing(int scripts, int rounds) throws Exception {
        CamelContext camel = context();
        Exchange exchange = exchange(camel);
        Language groovy = camel.resolveLanguage("groovy");
        List<Expression> expressions = new ArrayList<>();
        List<WeakReference<Class<?>>> classes = new ArrayList<>();
        for (int i = 0; i < scripts; i++) {
            Expression e = groovy.createExpression("getClass() // soft-" + i);
            expressions.add(e);
            classes.add(new WeakReference<>(e.evaluate(exchange, Class.class)));
        }
        for (int r = 1; r <= rounds; r++) {
            // a soft reference is only cleared when it was not used since the previous GC, hence two collections
            System.gc();
            System.gc();
            int recompiled = 0;
            long start = System.nanoTime();
            for (int i = 0; i < scripts; i++) {
                Class<?> c = expressions.get(i).evaluate(exchange, Class.class);
                if (c != classes.get(i).get()) {
                    recompiled++;
                    classes.set(i, new WeakReference<>(c));
                }
            }
            line("softReferenceClearing round=%d scripts=%d recompiledAfterGc=%d evaluationTime=%.2f ms",
                    r, scripts, recompiled, (System.nanoTime() - start) / 1_000_000.0);
        }
        camel.stop();
    }

    private static CamelContext context() throws Exception {
        CamelContext camel = new DefaultCamelContext();
        camel.start();
        return camel;
    }

    private static Exchange exchange(CamelContext camel) {
        Exchange exchange = new DefaultExchange(camel);
        exchange.getIn().setBody("World");
        return exchange;
    }

    private static Set<Class<?>> identitySet() {
        return Collections.newSetFromMap(new IdentityHashMap<>());
    }

    private static long metaspaceUsedAfterGc() {
        System.gc();
        System.gc();
        return metaspaceUsed();
    }

    private static long metaspaceUsed() {
        for (MemoryPoolMXBean pool : ManagementFactory.getMemoryPoolMXBeans()) {
            if ("Metaspace".equals(pool.getName())) {
                return pool.getUsage().getUsed();
            }
        }
        return -1;
    }

    private static double mb(long bytes) {
        return bytes / 1024.0 / 1024.0;
    }

    private void line(String format, Object... args) {
        report.append(String.format(format, args)).append('\n');
    }
}

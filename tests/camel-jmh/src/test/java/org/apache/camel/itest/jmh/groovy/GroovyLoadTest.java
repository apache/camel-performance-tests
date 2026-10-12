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
import java.io.PrintWriter;
import java.lang.management.ClassLoadingMXBean;
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryPoolMXBean;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicLongArray;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.LongAdder;
import java.util.concurrent.locks.LockSupport;

import javax.management.NotificationEmitter;
import javax.management.openmbean.CompositeData;

import com.sun.management.GarbageCollectionNotificationInfo;
import com.sun.management.OperatingSystemMXBean;
import com.sun.management.ThreadMXBean;
import org.apache.camel.CamelContext;
import org.apache.camel.Endpoint;
import org.apache.camel.Exchange;
import org.apache.camel.Expression;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.builder.RouteBuilder;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.camel.language.jactl.JactlLanguage;
import org.apache.camel.language.python3.Python3Language;
import org.apache.camel.support.ExpressionAdapter;
import org.junit.jupiter.api.Test;

import static org.apache.camel.itest.jmh.groovy.GroovyBenchmarkSupport.check;

/**
 * Long running, high load comparison of the same route in Java and Groovy, focused on heap behaviour. Not a JMH
 * benchmark: producer threads push messages through the route for {@code load.duration} seconds while a sampler records,
 * every {@code load.interval} seconds, throughput, latency, allocation rate, heap/old generation occupancy after GC, GC
 * pauses, Metaspace and class loading into a CSV file.
 * <p>
 * Route: filter(amount > 100) -> setHeader(vip = any line item > 90) -> setBody('order-' + amount + '-' + vip) ->
 * counter. Variants ({@code load.variant}):
 * <ul>
 * <li>java - Java predicate/expressions</li>
 * <li>groovy - groovy predicate/expressions</li>
 * <li>groovyPrototype - same scripts through the benchmark-local {@link OptimizedGroovyExpression} (lazy binding)</li>
 * <li>groovyManyScripts - like groovy, but setBody picks one of {@code load.scripts} distinct scripts per message, as an
 * application with many groovy expressions would (more than the 1000 entry script cache)</li>
 * <li>jactl, javaLanguage (jOOR), mvel, js (GraalJS), python3 (GraalPy), quickjs (QuickJS4J) - the same route in the
 * other scripting languages; quickjs works on a JSON snapshot of the body ({@code body.lineItems[].value}) instead of
 * the Order object, so it needs no host access</li>
 * </ul>
 * Example (the JVM flags go to the surefire JVM that runs the load):
 *
 * <pre>
 * mvn test -P jmh -Dtest=GroovyLoadTest -Dload.variant=groovy -Dload.duration=600 \
 *   -DargLine="-Xms1g -Xmx1g -Xlog:gc*:file=groovy-gc.log:time,uptime,level,tags -XX:StartFlightRecording=filename=groovy.jfr,settings=profile"
 * </pre>
 */
public class GroovyLoadTest {

    private static final int BUCKETS_US = 1000;
    private static final int BUCKETS = BUCKETS_US + 10_000;

    private final LongAdder processed = new LongAdder();
    private final LongAdder sent = new LongAdder();
    private final AtomicReference<Throwable> failure = new AtomicReference<>();
    private final AtomicLong gcPauseCount = new AtomicLong();
    private final AtomicLong gcPauseNanosTotal = new AtomicLong();
    private final AtomicLong gcPauseMaxMillis = new AtomicLong();
    private final AtomicLong fullGcCount = new AtomicLong();
    private final AtomicLong oldGenAfterLastGc = new AtomicLong(-1);

    @Test
    public void launchBenchmark() throws Exception {
        String variant = System.getProperty("load.variant", "groovy");
        int threads = Integer.getInteger("load.threads", 8);
        int duration = Integer.getInteger("load.duration", 60);
        int interval = Integer.getInteger("load.interval", 5);
        int warmup = Integer.getInteger("load.warmup", Math.min(60, duration / 5));
        long rate = Long.getLong("load.rate", 0L);
        int scripts = Integer.getInteger("load.scripts", 1500);
        String dir = System.getProperty("jmh.resultDir", ".");
        String name = "GroovyLoadTest-" + variant + (rate > 0 ? "-rate" + rate : "") + System.getProperty("jmh.suffix", "");
        new File(dir).mkdirs();

        CamelContext camel = new DefaultCamelContext();
        boolean features = variant.startsWith("features-");
        // the body is a Java object: the sandboxed languages need host access to call its getters
        if (features) {
            FeatureRoutes.configure(camel, variant.substring("features-".length()));
        } else if ("jactl".equals(variant)) {
            camel.getRegistry().bind("jactl", JactlLanguage.createWithHostAccess());
        } else if ("python3".equals(variant)) {
            camel.getRegistry().bind("python3", Python3Language.createWithHostAccess());
        }
        camel.addRoutes(features ? FeatureRoutes.route(variant.substring("features-".length()), processed::increment)
                : route(variant, scripts));
        camel.start();
        ProducerTemplate template = camel.createProducerTemplate();
        Endpoint endpoint = camel.getEndpoint("direct:load");

        Order[] orders = new Order[64];
        for (int i = 0; i < orders.length; i++) {
            orders[i] = Order.create(20, i % 2 == 0);
        }
        List<Map<String, Object>> headers = new ArrayList<>();
        for (int amount = 0; amount < 200; amount++) {
            headers.add(Map.of("amount", amount));
        }
        if (features) {
            Exchange out = template.request(endpoint, e -> {
                e.getMessage().setBody(orders[0]);
                e.getMessage().setHeaders(headers.get(150));
            });
            FeatureRoutes.assertProcessed(out, 150, true,
                    orders[0].getLineItems().stream().mapToInt(LineItem::getValue).sum());
            out = template.request(endpoint, e -> {
                e.getMessage().setBody(orders[1]);
                e.getMessage().setHeaders(headers.get(150));
            });
            FeatureRoutes.assertProcessed(out, 150, false,
                    orders[1].getLineItems().stream().mapToInt(LineItem::getValue).sum());
        } else {
            check(variant, "order-150-true", template.requestBodyAndHeaders(endpoint, orders[0], headers.get(150)));
            check(variant, "order-150-false", template.requestBodyAndHeaders(endpoint, orders[1], headers.get(150)));
        }
        check(variant + "(filtered)", orders[0], template.requestBodyAndHeaders(endpoint, orders[0], headers.get(50)));
        processed.reset();

        installGcListener();
        // one histogram per producer thread, merged by the sampler, so recording adds no cross-thread contention
        AtomicLongArray[] latency = new AtomicLongArray[threads];
        for (int t = 0; t < threads; t++) {
            latency[t] = new AtomicLongArray(BUCKETS);
        }
        long start = System.nanoTime();
        long deadline = start + TimeUnit.SECONDS.toNanos(duration);
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        List<Future<?>> futures = new ArrayList<>();
        for (int t = 0; t < threads; t++) {
            final int seed = t;
            futures.add(pool.submit(() -> {
                AtomicLongArray histogram = latency[seed];
                try {
                    long period = rate > 0 ? TimeUnit.SECONDS.toNanos(1) * threads / rate : 0;
                    long next = System.nanoTime();
                    long n = seed * 7919L;
                    while (failure.get() == null) {
                        long now = System.nanoTime();
                        if (now >= deadline) {
                            return null;
                        }
                        long sendStart;
                        if (period > 0) {
                            next += period;
                            if (next > now) {
                                LockSupport.parkNanos(next - now);
                            }
                            // latency from the intended send time, so a thread that falls behind is not hidden
                            // (no coordinated omission)
                            sendStart = next;
                        } else {
                            sendStart = System.nanoTime();
                        }
                        n++;
                        template.sendBodyAndHeaders(endpoint, orders[(int) (n & 63)], headers.get((int) (n * 31 % 200)));
                        record(histogram, System.nanoTime() - sendStart);
                        sent.increment();
                    }
                    return null;
                } catch (RuntimeException | Error e) {
                    failure.compareAndSet(null, e);
                    throw e;
                }
            }));
        }

        File csv = new File(dir, name + ".csv");
        long[] steadyHistogram = new long[BUCKETS];
        Summary summary = new Summary();
        try (PrintWriter out = new PrintWriter(csv)) {
            out.println("seconds,msgPerSec,p50us,p99us,p999us,maxBucketUs,allocMBPerSec,allocBytesPerMsg,heapUsedMB,"
                        + "oldGenUsedMB,oldGenAfterGcMB,gcPauses,gcPauseTotalMs,gcPauseMaxMs,fullGcs,metaspaceMB,"
                        + "classesLoadedTotal,classesUnloadedTotal,processCpuLoad");
            Sample previous = Sample.take(sent.sum(), 0, oldGenAfterLastGc.get());
            while (System.nanoTime() < deadline && failure.get() == null) {
                Thread.sleep(TimeUnit.SECONDS.toMillis(interval));
                long elapsed = TimeUnit.NANOSECONDS.toSeconds(System.nanoTime() - start);
                Sample current = Sample.take(sent.sum(), elapsed, oldGenAfterLastGc.get());
                long[] histogram = new long[BUCKETS];
                for (AtomicLongArray threadHistogram : latency) {
                    for (int i = 0; i < BUCKETS; i++) {
                        histogram[i] += threadHistogram.getAndSet(i, 0);
                    }
                }
                double seconds = (current.nanos - previous.nanos) / 1e9;
                long msgs = current.messages - previous.messages;
                long allocated = current.allocatedBytes - previous.allocatedBytes;
                long pauses = gcPauseCount.getAndSet(0);
                long pauseNanos = gcPauseNanosTotal.getAndSet(0);
                long pauseMax = gcPauseMaxMillis.getAndSet(0);
                long fullGcs = fullGcCount.getAndSet(0);
                out.printf("%d,%.0f,%d,%d,%d,%d,%.1f,%d,%.1f,%.1f,%.1f,%d,%.1f,%d,%d,%.1f,%d,%d,%.2f%n",
                        elapsed, msgs / seconds, percentile(histogram, 0.50), percentile(histogram, 0.99),
                        percentile(histogram, 0.999), maxBucket(histogram), allocated / seconds / 1024 / 1024,
                        msgs > 0 ? allocated / msgs : 0, mb(current.heapUsed), mb(current.oldGenUsed),
                        mb(current.oldGenAfterGc), pauses, pauseNanos / 1e6, pauseMax, fullGcs, mb(current.metaspace),
                        current.classesLoaded, current.classesUnloaded, current.processCpuLoad);
                out.flush();
                if (elapsed > warmup) {
                    for (int i = 0; i < BUCKETS; i++) {
                        steadyHistogram[i] += histogram[i];
                    }
                    summary.add(msgs, seconds, allocated, pauses, pauseNanos, pauseMax, fullGcs, current);
                }
                previous = current;
            }
        }
        if (failure.get() != null) {
            pool.shutdownNow();
            camel.stop();
            throw new AssertionError("A producer thread failed, the results are invalid", failure.get());
        }
        for (Future<?> f : futures) {
            f.get();
        }
        pool.shutdown();
        double passedFilter = 100.0 * processed.sum() / Math.max(1, sent.sum());
        template.stop();
        camel.stop();

        String text = String.format(
                "%s threads=%d duration=%ds warmupExcluded=%ds rate=%s jvm=%s args=%s%n"
                                    + "  throughput avg=%.0f msg/s sent (%.1f%% passed the filter), latency p50=%d us p99=%d us p99.9=%d us%n"
                                    + "  allocation avg=%.1f MB/s, %d bytes/msg%n"
                                    + "  gc pauses=%d (%.1f/s), pause total=%.0f ms (%.2f%% of wall time), max pause=%d ms, full gcs=%d%n"
                                    + "  old gen after gc: first=%.1f MB min=%.1f MB max=%.1f MB last=%.1f MB%n"
                                    + "  metaspace: first=%.1f MB last=%.1f MB, classes loaded +%d unloaded +%d, cpu avg=%.0f%%%n",
                variant, threads, duration, warmup, rate > 0 ? rate + " msg/s" : "unbounded",
                System.getProperty("java.vm.version"), ManagementFactory.getRuntimeMXBean().getInputArguments(),
                summary.messages / summary.seconds, passedFilter, percentile(steadyHistogram, 0.50),
                percentile(steadyHistogram, 0.99), percentile(steadyHistogram, 0.999),
                summary.allocated / summary.seconds / 1024 / 1024, summary.allocated / Math.max(1, summary.messages),
                summary.pauses, summary.pauses / summary.seconds, summary.pauseNanos / 1e6,
                summary.pauseNanos / 1e7 / summary.seconds, summary.pauseMax, summary.fullGcs,
                mb(summary.first.oldGenAfterGc), mb(summary.minOldAfterGc), mb(summary.maxOldAfterGc),
                mb(summary.last.oldGenAfterGc), mb(summary.first.metaspace), mb(summary.last.metaspace),
                summary.last.classesLoaded - summary.first.classesLoaded,
                summary.last.classesUnloaded - summary.first.classesUnloaded, summary.cpu / summary.samples * 100);
        Files.writeString(new File(dir, name + ".txt").toPath(), text);
        System.out.println(text);
    }

    private RouteBuilder route(String variant, int scripts) {
        return new RouteBuilder() {

            private void script(String language, String filter, String vip, String body) {
                from("direct:load").routeId("load")
                        .filter().language(language, filter)
                        .setHeader("vip").language(language, vip)
                        .setBody().language(language, body)
                        .process(e -> processed.increment());
            }

            @Override
            public void configure() {
                switch (variant) {
                    case "java" -> from("direct:load").routeId("load")
                            .filter(e -> e.getMessage().getHeader("amount", Integer.class) > 100)
                            .setHeader("vip", new ExpressionAdapter() {
                                @Override
                                public Object evaluate(Exchange e) {
                                    return e.getMessage().getBody(Order.class).getLineItems().stream()
                                            .anyMatch(i -> i.getValue() > 90);
                                }
                            })
                            .setBody(new ExpressionAdapter() {
                                @Override
                                public Object evaluate(Exchange e) {
                                    return "order-" + e.getMessage().getHeader("amount", Integer.class) + "-"
                                           + e.getMessage().getHeader("vip", Boolean.class);
                                }
                            })
                            .process(e -> processed.increment());
                    case "groovy" -> from("direct:load").routeId("load")
                            .filter().groovy("headers.amount > 100")
                            .setHeader("vip").groovy("body.lineItems.any { it.value > 90 }")
                            .setBody().groovy("'order-' + headers.amount + '-' + headers.vip")
                            .process(e -> processed.increment());
                    case "groovyPrototype" -> from("direct:load").routeId("load")
                            .filter(new OptimizedGroovyExpression("headers.amount > 100", true))
                            .setHeader("vip", new OptimizedGroovyExpression("body.lineItems.any { it.value > 90 }", true))
                            .setBody(new OptimizedGroovyExpression("'order-' + headers.amount + '-' + headers.vip", true))
                            .process(e -> processed.increment());
                    case "groovyManyScripts" -> {
                        Expression[] bodies = new Expression[scripts];
                        for (int i = 0; i < scripts; i++) {
                            bodies[i] = getContext().resolveLanguage("groovy")
                                    .createExpression("'order-' + headers.amount + '-' + headers.vip // script " + i);
                        }
                        AtomicLong next = new AtomicLong();
                        from("direct:load").routeId("load")
                                .filter().groovy("headers.amount > 100")
                                .setHeader("vip").groovy("body.lineItems.any { it.value > 90 }")
                                .setBody(new ExpressionAdapter() {
                                    @Override
                                    public Object evaluate(Exchange e) {
                                        return bodies[(int) (next.getAndIncrement() % scripts)].evaluate(e, Object.class);
                                    }
                                })
                                .process(e -> processed.increment());
                    }
                    case "jactl" -> script("jactl", "headers.amount > 100",
                            "body.getLineItems().anyMatch{ it.getValue() > 90 }",
                            "'order-' + headers.amount + '-' + headers.vip");
                    // explicit .class: jOOR does not rewrite the "Integer" shorthand in every position
                    case "javaLanguage" -> script("java", "headerAs('amount', Integer.class) > 100",
                            "bodyAs(org.apache.camel.itest.jmh.groovy.Order.class).getLineItems().stream().anyMatch(i -> i.getValue() > 90)",
                            "'order-' + headerAs('amount', Integer.class) + '-' + headerAs('vip', Boolean.class)");
                    case "mvel" -> script("mvel", "headers.amount > 100",
                            "($ in request.body.lineItems if $.value > 90).size() > 0",
                            "'order-' + headers.amount + '-' + headers.vip");
                    case "js" -> script("js", "headers.get('amount') > 100",
                            "body.getLineItems().stream().anyMatch(i => i.getValue() > 90)",
                            "'order-' + headers.get('amount') + '-' + headers.get('vip')");
                    case "python3" -> script("python3", "headers['amount'] > 100",
                            "any(i.getValue() > 90 for i in body.getLineItems())",
                            "'order-' + str(headers['amount']) + '-' + ('true' if headers['vip'] else 'false')");
                    case "quickjs" -> script("quickjs", "headers.amount > 100",
                            "body.lineItems.some(i => i.value > 90)",
                            "'order-' + headers.amount + '-' + headers.vip");
                    default -> throw new IllegalArgumentException("Unknown load.variant " + variant);
                }
            }
        };
    }

    private void installGcListener() {
        for (GarbageCollectorMXBean gc : ManagementFactory.getGarbageCollectorMXBeans()) {
            ((NotificationEmitter) gc).addNotificationListener((notification, handback) -> {
                if (!GarbageCollectionNotificationInfo.GARBAGE_COLLECTION_NOTIFICATION.equals(notification.getType())) {
                    return;
                }
                GarbageCollectionNotificationInfo info
                        = GarbageCollectionNotificationInfo.from((CompositeData) notification.getUserData());
                // every G1 bean reports stop-the-world pauses: "G1 Young Generation" (young and mixed), "G1 Old
                // Generation" (full) and, on JDK 20+, "G1 Concurrent GC" (Remark and Cleanup). GcInfo durations are
                // whole milliseconds, so sub-ms pauses are rounded down: exact figures come from the GC log.
                long millis = info.getGcInfo().getDuration();
                // the old generation occupancy after every pause (the pool's collection usage only changes on
                // mixed/full collections)
                info.getGcInfo().getMemoryUsageAfterGc().forEach((pool, usage) -> {
                    if (pool.contains("Old Gen") || pool.contains("Tenured")) {
                        oldGenAfterLastGc.set(usage.getUsed());
                    }
                });
                gcPauseCount.incrementAndGet();
                gcPauseNanosTotal.addAndGet(TimeUnit.MILLISECONDS.toNanos(millis));
                gcPauseMaxMillis.accumulateAndGet(millis, Math::max);
                if (info.getGcAction().contains("major")) {
                    fullGcCount.incrementAndGet();
                }
            }, null, null);
        }
    }

    private static void record(AtomicLongArray histogram, long nanos) {
        // at a fixed rate the latency is measured from the scheduled send slot, which a producer can beat by a few ms
        long us = Math.max(0, nanos / 1000);
        int bucket = us < BUCKETS_US ? (int) us : (int) Math.min(BUCKETS - 1, BUCKETS_US + (us - BUCKETS_US) / 100);
        histogram.incrementAndGet(bucket);
    }

    private static long bucketUs(int bucket) {
        return bucket < BUCKETS_US ? bucket : BUCKETS_US + (bucket - BUCKETS_US) * 100L;
    }

    private static long percentile(long[] histogram, double p) {
        long total = 0;
        for (long c : histogram) {
            total += c;
        }
        long target = (long) Math.ceil(total * p);
        long seen = 0;
        for (int i = 0; i < histogram.length; i++) {
            seen += histogram[i];
            if (seen >= target && total > 0) {
                return bucketUs(i);
            }
        }
        return 0;
    }

    private static long maxBucket(long[] histogram) {
        for (int i = histogram.length - 1; i >= 0; i--) {
            if (histogram[i] > 0) {
                return bucketUs(i);
            }
        }
        return 0;
    }

    private static double mb(long bytes) {
        return bytes / 1024.0 / 1024.0;
    }

    private static final class Sample {
        long nanos;
        long seconds;
        long messages;
        long allocatedBytes;
        long heapUsed;
        long oldGenUsed;
        long oldGenAfterGc;
        long metaspace;
        long classesLoaded;
        long classesUnloaded;
        double processCpuLoad;

        static Sample take(long messages, long seconds, long oldGenAfterLastGc) {
            Sample s = new Sample();
            s.oldGenAfterGc = oldGenAfterLastGc;
            s.nanos = System.nanoTime();
            s.seconds = seconds;
            s.messages = messages;
            // sum over live threads (JDK 17 compatible); the producer threads live for the whole run
            ThreadMXBean threads = (ThreadMXBean) ManagementFactory.getThreadMXBean();
            for (long bytes : threads.getThreadAllocatedBytes(threads.getAllThreadIds())) {
                if (bytes > 0) {
                    s.allocatedBytes += bytes;
                }
            }
            s.heapUsed = ManagementFactory.getMemoryMXBean().getHeapMemoryUsage().getUsed();
            for (MemoryPoolMXBean pool : ManagementFactory.getMemoryPoolMXBeans()) {
                if (pool.getName().contains("Old Gen")) {
                    s.oldGenUsed = pool.getUsage().getUsed();
                } else if ("Metaspace".equals(pool.getName())) {
                    s.metaspace = pool.getUsage().getUsed();
                }
            }
            ClassLoadingMXBean cl = ManagementFactory.getClassLoadingMXBean();
            s.classesLoaded = cl.getTotalLoadedClassCount();
            s.classesUnloaded = cl.getUnloadedClassCount();
            s.processCpuLoad = ((OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean()).getProcessCpuLoad();
            return s;
        }
    }

    private static final class Summary {
        long messages;
        double seconds;
        long allocated;
        long pauses;
        long pauseNanos;
        long pauseMax;
        long fullGcs;
        long minOldAfterGc = Long.MAX_VALUE;
        long maxOldAfterGc;
        double cpu;
        int samples;
        Sample first;
        Sample last;

        void add(long msgs, double secs, long alloc, long gcPauses, long gcPauseNanos, long gcPauseMax, long full, Sample s) {
            messages += msgs;
            seconds += secs;
            allocated += alloc;
            pauses += gcPauses;
            pauseNanos += gcPauseNanos;
            pauseMax = Math.max(pauseMax, gcPauseMax);
            fullGcs += full;
            minOldAfterGc = Math.min(minOldAfterGc, s.oldGenAfterGc);
            maxOldAfterGc = Math.max(maxOldAfterGc, s.oldGenAfterGc);
            cpu += s.processCpuLoad;
            samples++;
            if (first == null) {
                first = s;
            }
            last = s;
        }
    }
}

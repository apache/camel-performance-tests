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

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

import org.apache.camel.CamelContext;
import org.apache.camel.Processor;
import org.apache.camel.component.file.FileConsumer;
import org.apache.camel.component.file.FileEndpoint;
import org.apache.camel.component.file.GenericFile;
import org.apache.camel.component.file.GenericFileOperations;
import org.apache.camel.component.file.GenericFileProcessStrategy;
import org.apache.camel.impl.DefaultCamelContext;
import org.junit.jupiter.api.Test;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;

/**
 * Tests the {@link org.apache.camel.component.file.FileConsumer#pollDirectory} method
 */
@State(Scope.Thread)
public class FileComponentPollingDirectoryTest {
    private MyFileEndpoint endpoint;
    private CustomFileConsumer consumer;
    @Param(".")
    private String inputDir;

    private int depth = 1;
    private int subDirs = 5;
    private int numFiles = 20000;

    private List<GenericFile<File>> fileList = new ArrayList<>();


    private class CustomFileConsumer extends FileConsumer {
        public CustomFileConsumer(FileEndpoint endpoint, Processor processor, GenericFileOperations<File> operations, GenericFileProcessStrategy<File> processStrategy) {
            super(endpoint, processor, operations, processStrategy);
        }

        @Override
        public boolean pollDirectory(String fileName, List<GenericFile<File>> fileList, int depth) {
            return super.pollDirectory(fileName, fileList, depth);
        }
    }

    private class MyFileEndpoint extends FileEndpoint {
        @Override
        protected FileConsumer newFileConsumer(Processor processor, GenericFileOperations<File> operations) {
            return new CustomFileConsumer(this, processor, operations, createGenericFileStrategy());
        }
    }

    public String createFakeFiles() throws Exception {
        Path baseDir = Paths.get(this.getClass().getResource(".").getFile(), "file-component-test-data");
        baseDir = Files.createDirectories(baseDir);

        for (int d = 0; d < depth; d++) {
            Path testDir = Files.createTempDirectory(baseDir, "file-component");
            for (int i = 0; i < subDirs; i++) {
                Path subDir = Files.createTempDirectory(testDir, "file-component");
                for (int f = 0; f < numFiles; f++) {
                    Files.createTempFile(subDir, "tmp", "test");
                }
            }
        }

        return baseDir.toString();
    }

    @Setup
    public void prepare() throws Exception {
        CamelContext context = new DefaultCamelContext();
        endpoint = new MyFileEndpoint();
        endpoint.setNoop(true);
        endpoint.setRecursive(true);

        System.out.println("Running with Camel version: " + context.getVersion());

        context.addEndpoint("perf-file", endpoint);
        consumer = (CustomFileConsumer) endpoint.newFileConsumer(exchange -> {}, null);
    }


    @Benchmark
    public void testFilePolling() {
        System.out.println("Polling from " + inputDir);
        consumer.pollDirectory(inputDir, fileList, 0);
        System.out.println("Polled files: " + fileList.size());
    }

    @Test
    public void launchBenchmark() throws Exception {
        String inputDir = createFakeFiles();

        Options opt = new OptionsBuilder()
                .include(this.getClass().getName() + ".*")
                .mode(Mode.SingleShotTime)
                .timeUnit(TimeUnit.MILLISECONDS)
                .forks(15)
                .shouldFailOnError(true)
                .shouldDoGC(true)
                .param("inputDir", inputDir)
                .build();

        new Runner(opt).run();
    }
}

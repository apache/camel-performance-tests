# Apache Camel Performance Tests

This project provides performance tests for Apache Camel.

## Running the Performance Tests

### Camel JMH

The performance tests located in the `camel-jmh` module can be run using the following command:

```bash
mvn -l camel-${version}-jmh-test.log -DargLine="-XX:+UseNUMA -Xmx4G -Xms4G -server" -Dcamel.version=${version} -Pjmh -Dtest=${TESTS}  clean test
```

Where:
* `${version}` is the Apache Camel version to use.
* `${TESTS}` is a comma-separated list of tests to run (e.g., `AggregatorTest,ContentBasedRouterBodyTest`).

After running the tests, the results are stored in JMH JSON files (i.e.: `<test name>.jmh.json`).

## AI benchmark

The `ai-benchmark` directory holds a harness that measures how well an AI model builds and edits Camel integrations
through the Camel MCP server, scored by what runs. See [ai-benchmark/README.md](ai-benchmark/README.md) and the
blog post https://camel.apache.org/blog/2026/09/camel-local-model-benchmark/ for the first series.

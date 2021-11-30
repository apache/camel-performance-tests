## Camel Performance - Timer Log

This is a small demo application that is used for cpu and memory profiling the
internal Camel routing engine.

The demo uses a timer to trigger 1000 msg/sec that gets routed by Camel.
The demo does not use any networking or external services. This is on purpose
to focus profiling the internals of Camel - more specific the routing engine.

### Profiling

The demo can be run with `mvn camel:run` or by running the `MyApplication.java`
main class (from an IDE you can right-click this file and Run...).

A profile such as _YourKit_ or _JDK mission control_ can be attached to
the running application and manually profiled.

The application can be configured in `application.properties` such as
the functionality to turn on|off the pooling of exchanges (and other objects).

### Monitoring

After running this demo a camel-recording-*.jfr recording is generated, it is possible to plot jfr metrics to grafana following these steps:

* Start jfr-datasource and grafana with preconfigured datasource and dashboard

```
cd ../monitoring
docker-compose up
```

* Post recording to jfr-datasource

```
curl -F "file=@/camel-recording-*.jfr" "localhost:8080/load"
```

* wait 20s so that grafana will poll metrics from jfr-datsource
* go to grafana `http://localhost:3000` dashboard camel-jfr to observe results (default login is admin/admin)
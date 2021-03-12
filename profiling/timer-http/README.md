## Camel Performance - Timer HTTP

This is a small demo application that is used for cpu and memory profiling the HTTP component.

The demo uses a timer to trigger 1000 msg/sec that calls a HTTP service.


### Profiling

At first start the HTTP service using docker:

    docker run -p 5678:5678 hashicorp/http-echo -text="hello world"

Then the demo can be run with `mvn camel:run` or by running the `MyApplication.java`
main class (from an IDE you can right-click this file and Run...).

A profile such as _YourKit_ or _JDK mission control_ can be attached to
the running application and manually profiled.

The application can be configured in `application.properties` such as
the functionality to turn on|off the pooling of exchanges (and other objects).


# camel-performance-test-monitoring

* execute test in https://github.com/apache/camel-performance-tests/tree/main/profiling that generates a .jfr file record
* run `docker-compse up` in order to start jfr-datasource and grafana with preconfigured datasource and dashboard
* run `curl -F "file=@/path/to/recording.jfr" "localhost:8080/load"` where `/path/to/recording.jfr` is the path to the jfr generated in step 1
* wait 20s so that grafana will poll metrics from jfr-datsource
* go to grafana `http://localhost:3000` dashboard camel-jfr to observe results (default user is admin/admin)

# Kafka to S3 with YAML and Camel-Quarkus

build:
```shell script
./mvnw package
```

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    -e AWS_ACCESS_KEY=<access_key> \
    -e AWS_SECRET_KEY=<secret_key> \
    --network="host" \
    quay.io/camel/kafka-s3:1.0-SNAPSHOT-jvm
```

You'll need a running Kafka broker locally on your host.

## Enabling JFR 

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -v $PWD/jfr:/work/jfr:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    -e AWS_ACCESS_KEY=<access_key> \
    -e AWS_SECRET_KEY=<secret_key> \
    --network="host" \
    quay.io/camel/kafka-s3:1.0-SNAPSHOT-jvm
```

You'll need a running Kafka broker locally on your host.

Now you can start JFR with the following command

```
docker exec -it <container_id> jcmd 1 JFR.start name=Test settings=jfr/settings_for_heap.jfc duration=5m filename=jfr/output.jfr
```

and check the status

```
docker exec -it <container_id> jcmd 1 JFR.check
```


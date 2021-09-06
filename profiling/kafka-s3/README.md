# camel-k-runtime-example-kafka-s3

In the routes.yaml file, set correctly the AWS credentials for your S3 bucket.

build:
```shell script
./mvnw package
```

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    --network="host" \
    quay.io/oscerd/camel-k-runtime-example-kafka-s3:1.8.0-jvm
```

You'll need a running Kafka broker locally on your host.

## Enabling JFR 

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -v $PWD/jfr:/work/jfr:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    --network="host" \
    quay.io/oscerd/camel-k-runtime-example-kafka-s3:1.8.0-jvm
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


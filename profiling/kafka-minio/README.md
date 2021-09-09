# Kafka to Minio

First of all run the command to start Minio

```shell script
docker run -e MINIO_ROOT_USER=minio -e MINIO_ROOT_PASSWORD=miniostorage --net=host minio/minio server /data --console-address ":9001"
```

In the routes.yaml file, set correctly the Minio credentials for your bucket.

build:
```shell script
./mvnw clean package
```

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    --network="host" \
    quay.io/oscerd/kafka-minio:1.0-SNAPSHOT-jvm
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
    quay.io/oscerd/kafka-minio:1.0-SNAPSHOT-jvm
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

You'll need also kafkacat to be able to inject the filename header:

```
echo "payload" | ./kafkacat -b localhost:9092 -t testtopic -H "file=$(cat /dev/urandom | tr -dc '[:alpha:]' | fold -w ${1:-20} | head -n 1)"
```


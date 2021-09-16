# Kafka to Minio

First of all run the command to start Minio

```shell script
docker run -e MINIO_ROOT_USER=minio -e MINIO_ROOT_PASSWORD=miniostorage --net=host minio/minio server /data --console-address ":9001"
```

In the routes.yaml file, set correctly the Minio credentials for your bucket.

Also you'll need to run a Kafka cluster to point to. In this case you could use an ansible role like https://github.com/oscerd/kafka-ansible-role

And set up a file deploy.yaml with the following content:

```yaml
- name: role kafka
  hosts: localhost
  remote_user: user
  
  roles:
    - role: kafka-ansible-role
      kafka_version: 2.8.0
      path_dir: /home/user/
      unarchive_dest_dir: /home/user/kafka/demo/
      start_kafka: true
```

and then run

```shell script
ansible-playbook -v deploy.yaml
```

This should start a Kafka instance for you, on your local machine.

build:
```shell script
./mvnw clean package
```

At this point you're able to run the example:

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    --network="host" \
    quay.io/oscerd/kafka-minio:1.0-SNAPSHOT-jvm
```

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

You'll need also kafkacat to be able to inject the filename header and use the burst script

```shell script
export KAFKACAT_PATH=<path_to_your_kafkacat>
```

And now run the burst script.

This command for example will send 1000 messages with payload "payload" to the topic "testtopic"

```shell script
cd script/
> ./burst.sh -b localhost:9092 -n 1000 -t testtopic -p "payload"
```




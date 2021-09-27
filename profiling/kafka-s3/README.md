# camel-k-runtime-example-kafka-s3

In the routes.yaml file, set correctly the AWS credentials for your S3 bucket.

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
./mvnw package
```

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    --network="host" \
    quay.io/oscerd/kafka-s3:1.0-SNAPSHOT-jvm
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
    quay.io/oscerd/kafka-s3:1.0-SNAPSHOT-jvm
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


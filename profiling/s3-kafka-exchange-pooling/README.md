# S3 to Kafka

First of all install the AWS Cli https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html

Now we are able to use the s3-bulk script during the profiling.

In the routes.yaml file, set correctly the AWS S3 credentials for your bucket.

Create the camel-kafka-connector bucket on your AWS Account.

Now we can use the s3-bulk.sh script

```shell script
./s3-bulk.sh -f msg1.txt -b camel-kafka-connector -n 10000
```

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

If you want to have JFR enable from the beginning:

build:
```shell script
./mvnw clean package -Pjfr
```

At this point you're able to run the example:

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    --network="host" \
    quay.io/oscerd/s3-kafka:1.0-SNAPSHOT-jvm
```

## Enabling JFR 

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -v $PWD/jfr:/work/jfr:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    --network="host" \
    quay.io/oscerd/s3-kafka:1.0-SNAPSHOT-jvm
```

Now you can start JFR with the following command

```
docker exec -it <container_id> jcmd 1 JFR.start name=Test settings=jfr/settings_for_heap.jfc duration=5m filename=jfr/output.jfr
```

and check the status

```
docker exec -it <container_id> jcmd 1 JFR.check
```

## Enabling Async Profiler 

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -v async_profiler_path:/work/async-profiler:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    --network="host" \
    quay.io/oscerd/s3-kafka:1.0-SNAPSHOT-jvm
```

Where async profiler path is the path of your async profiler on your host machine.

Now you can start Async Profiler with the following command

```
docker exec -it <container_id> /work/async-profiler/profiler.sh -e alloc -d 30 -f /work/async-profiler/alloc_profile.html 1
```

This command while create an allocation flamegraph for the duration of 30 second of the running application.

The privileged option for running the docker container is the fastest way to have perf events syscall enabled.

If you don't want to use privileged approach, you can have a look at the basic configuration of async profiler (https://github.com/jvm-profiling-tools/async-profiler/wiki/Basic-Usage)

## Tuning Container

You could also modify the resources of your container with memory and cpu defined while running it

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -v $PWD/jfr:/work/jfr:Z \ 
    -e CAMEL_K_CONF=/etc/camel/application.properties \ 
    --network="host" \ 
    -m 128m \ 
    --cpu-quota="25000" \ 
    quay.io/oscerd/s3-kafka:1.0-SNAPSHOT-jvm
```

In this case we are allocating 128 Mb Memory to the container and 0.25% cpus.

## HEAP Sizing

In the pom you can also set a different Heap Size. The default is 128 Mb.




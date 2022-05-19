# Kafka to Minio with Exchange Pooling

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
    quay.io/oscerd/kafka-minio-exchange-pooling:1.0-SNAPSHOT-jvm
```

## Enabling JFR while running application

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -v $PWD/jfr:/work/jfr:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    --network="host" \
    quay.io/oscerd/kafka-minio-exchange-pooling:1.0-SNAPSHOT-jvm
```

Now you can start JFR with the following command

```
docker exec -it <container_id> jcmd 1 JFR.start name=Test settings=jfr/settings_for_heap.jfc duration=5m filename=jfr/output.jfr
```

and check the status

```
docker exec -it <container_id> jcmd 1 JFR.check
```

## Enabling Async Profiler while running application

docker:
```shell script
docker run --rm -ti \
    -v $PWD/data:/etc/camel:Z \
    -v async_profiler_path:/work/async-profiler:Z \
    -e CAMEL_K_CONF=/etc/camel/application.properties \
    --network="host" \
    quay.io/oscerd/kafka-minio-exchange-pooling:1.0-SNAPSHOT-jvm
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
    quay.io/oscerd/kafka-minio-exchange-pooling:1.0-SNAPSHOT-jvm
```

In this case we are allocating 128 Mb Memory to the container and 0.25% cpus.

## Running this profiling example with Camel-Jbang

You could also leveraging the camel-jbang module. From Camel 3.15.0 (still to be released) it will support the profiling feature.

What you need to do is simply running this commands:

```shell script
jbang  -Dcamel.jbang.version=3.18.0-SNAPSHOT  camel@apache/camel run --jfr-profile=profile data/sources/camel-jbang-route.yaml
```

You'll get at jfr recording file once the application will be stopped in your working directory.

## Send messages to Kafka

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

You could also tests this approach with multiple producers, through the multiburst script

```shell script
cd script/
> ./multiburst.sh -s 5 -b localhost:9092 -n 1000 -t testtopic -p "payload"
```

This command will run 5 burst script with 1000 messages each one with payload "payload" to the Kafka instance running on localhost:9092 and the topic "testtopic"

### Monitoring with Grafana

After running this performance test an output.jfr recording is generated in jfr folder, it is possible to plot jfr metrics to grafana following these steps:

Start jfr-datasource and grafana with preconfigured datasource and dashboard

```
cd ../monitoring
docker-compose up
```

Post recording to jfr-datasource

```
curl -F "file=@./jfr/output.jfr" "localhost:8080/load"
```

Now wait 20s so that grafana will poll metrics from jfr-datsource

And then go to grafana `http://localhost:3000` dashboard camel-jfr to observe results (default login is admin/admin)


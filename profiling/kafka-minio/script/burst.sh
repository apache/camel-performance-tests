#!/bin/bash
for i in {1..10000}
do
   echo "payload" | $KAFKACAT_PATH -b localhost:9092 -t testtopic -H "file=$(cat /dev/urandom | tr -dc '[:alpha:]' | fold -w ${1:-20} | head -n 1)"
done

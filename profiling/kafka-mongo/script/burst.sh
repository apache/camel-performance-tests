#!/bin/bash

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
    -n|--number)
      NUMBER="$2"
      shift # past argument
      shift # past value
      ;;
    -t|--topic)
      TOPIC="$2"
      shift # past argument
      shift # past value
      ;;
    -p|--payload)
      PAYLOAD="$2"
      shift # past argument
      shift # past value
      ;;
    -b|--broker)
      BROKER="$2"
      shift # past argument
      shift # past value
      ;;
    --default)
      DEFAULT=YES
      shift # past argument
      ;;
    *)    # unknown option
      POSITIONAL+=("$1") # save it in an array for later
      shift # past argument
      ;;
  esac
done

set -- "${POSITIONAL[@]}" # restore positional parameters

for i in $(seq 1 $NUMBER)
do
   echo $PAYLOAD | $KAFKACAT_PATH -b $BROKER -t $TOPIC 
done

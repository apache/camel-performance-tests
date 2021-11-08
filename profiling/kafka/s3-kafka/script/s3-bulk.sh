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
    -b|--bucket)
      BUCKET="$2"
      shift # past argument
      shift # past value
      ;;
    -f|--filename)
      FILENAME="$2"
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
   aws s3 cp $FILENAME s3://$BUCKET/$(cat /dev/urandom | tr -dc '[:alpha:]' | fold -w ${1:-20} | head -n 1).txt
done

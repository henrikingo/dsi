#!/bin/bash

export CLUSTER=$1

if [ ! $CLUSTER ]
then
    echo "Usage: $0 single|replica|shard|longevity|<cluster type>"
    exit -1
fi

# Terraform wants to run with the config files in the work directory.
cd clusters/$CLUSTER

cp ../../terraform/* .

# create all resources and instances
if [ $CLUSTER == "shard" -o $CLUSTER == "longevity" ]
then
# Shard cluster
./terraform apply -var="count=3"  | tee terraform.log

# workaround for failure to bring up all at the same time
./terraform apply -var="count=9" | tee -a terraform.log
else
# Most cluster types
./terraform apply  | tee terraform.log
fi

# just to print out disk i/o information
cat terraform.log | grep "  clat ("

if [ $CLUSTER != "longevity" -o $CLUSTER != "windows-single" ]
then
# check performance and re-done the mongod instance if necessary
../../bin/pre-qualify-cluster.sh
rc=$?
fi

if [ $CLUSTER == "shard" -o $CLUSTER == "replica" -o $CLUSTER == "replica-correctness" -o $CLUSTER == "single-c3-4xlarge" -o $CLUSTER == "single-c3-2xlarge" ]
then
# disable system failure for these clusters
rc=0
fi

# this will extract all public and private IP address information into a file ips.sh
../../bin/env.sh

# Use the return code from pre-qualify-cluster.sh if there was one
if [[ $rc != 0 ]]; then exit $rc; fi

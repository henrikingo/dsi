#!/bin/bash

cp ../../terraform/* .

# create all resources and instances
./terraform apply -var="count=3"  | tee terraform.log

# workaround for failure to bring up all at the same time
./terraform apply -var="count=9" | tee -a terraform.log

cat terraform.log | grep "  clat ("

../../bin/pre-qualify-cluster.sh
rc=$?

# disable system failure for shard cluster 
rc=0 

# this will extract all public and private IP address information
./env.sh

# make sure exit with the non-zero return code
if [[ $rc != 0 ]]; then exit $rc; fi

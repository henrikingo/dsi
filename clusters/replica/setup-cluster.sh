#!/bin/bash

cp ../../terraform/* .

# create all resources and instances
./terraform apply  | tee terraform.log

# just to print out disk i/o information
cat terraform.log | grep "  clat ("

# check performance and re-done the mongod instance if necessary
../../bin/pre-qualify-cluster.sh


# this will extract all public and private IP address information
./env.sh

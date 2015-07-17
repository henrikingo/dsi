#!/bin/bash

cp ../../terraform/* .

# create all resources and instances
./terraform apply -var="count=3" > terraform.log

# workaround for failure to bring up all at the same time
./terraform apply -var="count=9" >> terraform.log

# this will extract all public and private IP address information
./env.sh

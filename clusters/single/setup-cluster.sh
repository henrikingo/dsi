#!/bin/bash

cp ../../terraform/* .

# create all resources and instances
./terraform apply  > t

# check performance and re-done the mongod instance if necessary


# this will extract all public and private IP address information
./env.sh

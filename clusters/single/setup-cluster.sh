#!/bin/bash

cp ../../terraform/* .

# create all resources and instances
./terraform apply 

# this will extract all public and private IP address information
./env.sh

#!/bin/bash

cp ../../terraform/* .

# create all resources and instances
./terraform apply  | tee terraform.log

# this will extract all public and private IP address information
./env.sh


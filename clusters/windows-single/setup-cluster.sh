#!/bin/bash

TERRAFORM="${TERRAFORM:-../../terraform/terraform}"

# create all resources and instances
$TERRAFORM apply  | tee terraform.log

# this will extract all public and private IP address information
./env.sh

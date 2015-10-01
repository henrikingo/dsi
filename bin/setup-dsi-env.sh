#!/bin/bash

set -e
set -v

# install terraform
mkdir keys
mkdir terraform
cd terraform
wget -nv --no-check-certificate https://s3-us-west-2.amazonaws.com/dsi-donot-remove/terraform/terraform_0.5.3.tar.gz -O - | tar zxv

# install workload wrapper
cd ../bin
wget -nv --no-check-certificate https://s3-us-west-2.amazonaws.com/dsi-donot-remove/mc/mc.tar.gz -O - | tar zxv
cd ..
ls

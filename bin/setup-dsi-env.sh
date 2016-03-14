#!/bin/bash

set -e
set -v

# install terraform
mkdir keys
mkdir terraform
cd terraform
curl  -O --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/terraform/terraform_0.6.12_linux.tar.gz
tar zxvf terraform_0.6.12_linux.tar.gz
mv terraform_0.6.12_linux_amd64/* .
rm terraform_0.6.12_linux.tar.gz

# install workload wrapper
cd ../bin
wget -nv --no-check-certificate https://s3-us-west-2.amazonaws.com/dsi-donot-remove/mc/mc.tar.gz -O - | tar zxv
cd ..
ls

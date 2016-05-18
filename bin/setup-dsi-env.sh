#!/bin/bash

set -e
set -v

export DSI_PATH=${DSI_PATH:-.}

# install terraform
mkdir -p keys
mkdir terraform

cd terraform
curl  -O --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/terraform/terraform_0.6.12_linux.tar.gz
tar zxvf terraform_0.6.12_linux.tar.gz
mv terraform_0.6.12_linux_amd64/* .
rm terraform_0.6.12_linux.tar.gz
cd ..

# install workload wrapper
pushd .
cd ${DSI_PATH}/bin
curl -O --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/mc/mc.tar.gz
tar zxvf mc.tar.gz
rm mc.tar.gz
popd

ls

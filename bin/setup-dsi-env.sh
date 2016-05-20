#!/bin/bash

set -e
set -v

export DSI_PATH=${DSI_PATH:-.}

# install terraform
mkdir -p keys
mkdir terraform

cd terraform
curl  -O --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/terraform/terraform_0.6.16_linux_amd64.zip
unzip terraform_0.6.16_linux_amd64.zip
cd ..

# install workload wrapper
pushd .
cd ${DSI_PATH}/bin
curl -O --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/mc/mc.tar.gz
tar zxvf mc.tar.gz
rm mc.tar.gz
popd

ls

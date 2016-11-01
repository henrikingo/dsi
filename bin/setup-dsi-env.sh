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

cp terraform/* work

# install workload wrapper
pushd .
cd ${DSI_PATH}/bin
curl --retry 10 https://s3.amazonaws.com/mciuploads/mission-control/linux/fbe18428a4b0c1055c7a847427d09bcec1d9b75b/mc-mission_control_linux_fbe18428a4b0c1055c7a847427d09bcec1d9b75b_16_11_01_15_36_42.tar.gz | tar -xvz
popd

sysctl vm.overcommit_memory
sysctl -w vm.overcommit_memory=1
sysctl vm.overcommit_memory

ls

# Install pip modules with virtualenv
virtualenv ./venv
source ./venv/bin/activate
pip install -r $DSI_PATH/requirements.txt

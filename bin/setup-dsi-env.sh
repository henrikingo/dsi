#!/bin/bash

set -e
set -v

export DSI_PATH=${DSI_PATH:-.}

# install terraform
mkdir terraform

cd terraform
curl  -O --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/terraform/terraform_0.6.16_linux_amd64.zip
unzip terraform_0.6.16_linux_amd64.zip
cd ..

cp terraform/* work

# install workload wrapper
pushd .
cd ${DSI_PATH}/bin
curl --retry 10 -o mc.tar.gz https://s3.amazonaws.com/mciuploads/mission-control/linux/f96a7694b93f19fc991f25cbc8b795fed12d86df/mc-mission_control_linux_f96a7694b93f19fc991f25cbc8b795fed12d86df_17_01_25_19_37_51.tar.gz
tar zxvf mc.tar.gz
popd

sysctl vm.overcommit_memory
sysctl -w vm.overcommit_memory=1
sysctl vm.overcommit_memory

ls

# Install pip modules with virtualenv
virtualenv ./venv
source ./venv/bin/activate
pip install -r $DSI_PATH/requirements.txt

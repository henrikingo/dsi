#!/bin/bash

set -e
set -v

export DSI_PATH=${DSI_PATH:-.}

# install terraform
mkdir terraform

cd terraform
curl  -O --retry 10 https://releases.hashicorp.com/terraform/0.10.4/terraform_0.10.4_linux_amd64.zip
unzip terraform_0.10.4_linux_amd64.zip
cd ..

cp terraform/terraform work

# install workload wrapper
pushd .
cd ${DSI_PATH}/bin
curl --retry 10 -o mc.tar.gz https://s3.amazonaws.com/mciuploads/mission-control/linux/513958123705b425da34ed8e133f13fc16a61a7b/mc-mission_control_linux_513958123705b425da34ed8e133f13fc16a61a7b_17_06_13_13_42_59.tar.gz
tar zxvf mc.tar.gz
popd

sysctl vm.overcommit_memory
sysctl -w vm.overcommit_memory=1
sysctl vm.overcommit_memory

ls

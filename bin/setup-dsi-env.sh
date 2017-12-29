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


# Note: These were added for mission-control and in particular its many threads doing logging.
# It's quite likely this is no longer needed.
sysctl vm.overcommit_memory
sysctl -w vm.overcommit_memory=1
sysctl vm.overcommit_memory

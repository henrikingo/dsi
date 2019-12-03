#!/bin/bash

set -e
set -v

export DSI_PATH=${DSI_PATH:-.}

# install terraform
mkdir terraform

cd terraform
curl  -O --retry 10 -fsS https://releases.hashicorp.com/terraform/0.12.16/terraform_0.12.16_linux_amd64.zip
unzip -q terraform_0.12.16_linux_amd64.zip
cd ..

cp terraform/terraform work


# Note: These were added for mission-control and in particular its many threads doing logging.
# It's quite likely this is no longer needed.
sysctl vm.overcommit_memory
sysctl -w vm.overcommit_memory=1
sysctl vm.overcommit_memory

#!/bin/bash

set -e
set -v

export DSI_PATH=${DSI_PATH:-.}

EVG_DATA_DIR="/data/infrastructure_provisioning"
if [ -d "$EVG_DATA_DIR" ]; then
	# If terraform-provider-docker is found, that means the older version
	# of terraform is being used since the new binary has everything packaged
	# into one.
	if [ -e $EVG_DATA_DIR/terraform/terraform-provider-docker ]; then
        # This only sets the TERRAFORM for all child processes.
        # Therefore it does not need to be set back to the original value.
		# infrastructure_teardown.sh should specifically use the old
		# terraform in EVG_DATA_DIR since the new terraform is not
		# backwards compatible
		export TERRAFORM=$EVG_DATA_DIR/terraform/terraform
		# Teardown the infrastructure since the new terraform binary will
		# not work properly with the old terraform files. Also remove
		# the old saved state once teardown is complete
		$EVG_DATA_DIR/terraform/infrastructure_teardown.sh && rm -rf "$EVG_DATA_DIR"
	fi
fi

# install terraform
mkdir terraform

cd terraform
curl  -O --retry 10 https://releases.hashicorp.com/terraform/0.9.11/terraform_0.9.11_linux_amd64.zip
unzip terraform_0.9.11_linux_amd64.zip
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

# Install pip modules with virtualenv
virtualenv ./venv
source ./venv/bin/activate
pip install -r $DSI_PATH/requirements.txt

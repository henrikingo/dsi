#!/bin/bash

# Destroy EC2 resources based on terraform.tfstate in current work directory

# Check if we are called by the Evergreen runner teardown hook, and if yes, cd into directory where state is saved.
MY_EVG_NAME="/data/infrastructure_provisioning/terraform/infrastructure_teardown.sh"
if [ $0 == $MY_EVG_NAME ]
then
    cd $(dirname $MY_EVG_NAME)
fi

TERRAFORM="${TERRAFORM:-./terraform}"
VARFILE=""
if [ -e cluster.json ]
then
    VARFILE="--var-file=cluster.json"
fi
yes yes | $TERRAFORM destroy $VARFILE

if [ $? != 0 ]
then
    # Something maybe wrong, try again
    yes yes | $TERRAFORM destroy $VARFILE
fi

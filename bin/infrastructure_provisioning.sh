#!/bin/bash
# Deploy a cluster, or reuse an existing one.
#
# If environment variable PRODUCTION is "true", then terraform.tfstate et.al. are stored and
# reused from /data/infrastructure_provisioning. Otherwise, just calls setup-cluster.sh to
# deploy a new cluster.

# don't run this with "set -e" so we can set up properly for infrastructure_teardown.sh
set +e

CLUSTER=$1

PRODUCTION="${PRODUCTION:-false}"
EXISTING="false"

BINDIR=$(dirname $0)
TERRAFORM="${TERRAFORM:-./terraform}"
TERRAFORM_DIR=$(dirname $TERRAFORM)

EVG_DATA_DIR="/data/infrastructure_provisioning"

if [ ! "$CLUSTER" ]
then
    echo "Usage: $0 single|replica|shard|longevity|<cluster type> [EXISTING=true|false]"
    exit -1
fi

# In Evergreen, the lifecycle of our EC2 cluster is tied to the life of the Evergreen runner instance.
# However, the directory all work happens in, is new for each task. We preserve terraform state info
# in a global location, outside the work directory.
if [ "$PRODUCTION" == "true" ]
then


    # instances are re-created for initialsync-logkeeper:
    if [[ -d "$EVG_DATA_DIR" && "$CLUSTER" == "initialsync-logkeeper" ]]; then
       echo "$0: $CLUSTER: force re-creation of instances (EXISTING=false) by executing teardown now."
       $EVG_DATA_DIR/terraform/infrastructure_teardown.sh && rm -rf "$EVG_DATA_DIR"
    fi

    # Create $EVG_DATA_DIR and copy executables into it
    if [ ! -d $EVG_DATA_DIR ]; then
        echo "Copying terraform binary to Evergreen host"
        mkdir $EVG_DATA_DIR
        # We want to copy the terraform dir (from parent dir) not just the terraform binary (from work dir)
        cp -r ../terraform $EVG_DATA_DIR
        cp -r ./modules $EVG_DATA_DIR/terraform
        echo "Copying infrastructure_teardown.sh to Evergreen host"
        cp "$BINDIR/infrastructure_teardown.sh" "$EVG_DATA_DIR/terraform/infrastructure_teardown.sh"
    fi
    echo "ls $EVG_DATA_DIR"
    ls -la $EVG_DATA_DIR
    echo "ls $EVG_DATA_DIR/terraform"
    ls -la $EVG_DATA_DIR/terraform

    # If terraform.tfstate file was saved and it represents the right $CLUSTER type, reuse those EC2 instances
    if [[ -e "$EVG_DATA_DIR/terraform/terraform.tfstate" && -e "$EVG_DATA_DIR/terraform/provisioned.$CLUSTER" ]]
    then
        EXISTING="true"
        echo "Retrieving terraform state for existing EC2 resources."
        cp "$EVG_DATA_DIR/terraform/terraform.tfstate" .
    else
        EXISTING="false"
        echo "No existing EC2 resources found."
    fi

fi

$DSI_PATH/bin/setup-cluster.sh $CLUSTER $EXISTING
rc=$?

if [ "$PRODUCTION" == "true" ]
then
    if [[ $rc -eq 0 ]]
    then
        echo "EC2 resources provisioned/updated successfully."
        echo "Will now save terraform state needed for teardown when triggered by the Evergreen runner."
        cp terraform.tfstate cluster.tf terraform.tfvars security.tf cluster.json aws_ssh_key.pem "$EVG_DATA_DIR/terraform"

        pushd .
        cd $EVG_DATA_DIR/terraform
            ./terraform get
            # Touch provisioned.$CLUSTER to indicate the type of cluster that was deployed by this Evergreen runner.
            rm provisioned.*
            touch provisioned.$CLUSTER
        popd

        echo "EC2 provisioning state saved on Evergreen host."
    else
        echo "Failed to provision EC2 resources. Releasing any EC2 resources that did deploy."
        infrastructure_teardown.sh
        rm -r $EVG_DATA_DIR
        echo "Cleaned up $EVG_DATA_DIR on Evergreen host. Exiting test."
        exit 1
    fi
fi

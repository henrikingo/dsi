#!/bin/bash

export CLUSTER=$1
export EXISTING="${2:-false}"
BINDIR=$(dirname $0)
TERRAFORM="${TERRAFORM:-./terraform}"

echo "TERRAFORM VERSION"
$TERRAFORM version

if [ ! "$CLUSTER" ]
then
    echo "Usage: $0 single|replica|shard|longevity|<cluster type> [EXISTING=true|false]"
    exit -1
fi

$TERRAFORM get --update
if [[ $? != 0 ]]
then
    exit 1
fi

$BINDIR/make_terraform_env.py --out-file cluster.json
if [[ $? != 0 ]]
then
    exit 1
fi

VAR_FILE=""
if [ -e "cluster.json" ]; then
    VAR_FILE="-var-file=cluster.json"
    echo "Using var_file ${VAR_FILE}"
fi

VAR=""

echo "EXISTING IS $EXISTING"
if [ $EXISTING == "true" ]; then
    echo "Reusing AWS cluster for $CLUSTER"
else
    echo "Create AWS cluster for $CLUSTER"
fi

# create all resources and instances
if [[ $EXISTING != "true"  && $CLUSTER == "shard"  ]]
then
    # Shard cluster
    # Note: mongod and mongod_ebs are treated differently, so we need to special case here.
    $TERRAFORM apply $VAR $VAR_FILE -var="mongod_ebs_instance_count=3"  | tee terraform.log

    # workaround for failure to bring up all at the same time
    $TERRAFORM apply $VAR $VAR_FILE -var="mongod_ebs_instance_count=9" | tee -a terraform.log
elif [[ $EXISTING != "true"  && $CLUSTER == "longevity"  ]] # This can be recombined with previous line if longevity is moved to ebs
then
    # Shard cluster
    $TERRAFORM apply $VAR $VAR_FILE -var="mongod_instance_count=3"  | tee terraform.log

    # workaround for failure to bring up all at the same time
    $TERRAFORM apply $VAR $VAR_FILE -var="mongod_instance_count=9" | tee -a terraform.log
elif [[ $EXISTING != "true"  && ( $CLUSTER == "initialsync-logkeeper" ) ]]
then
    # For initialsync-logkeeper cluster, create seeded_ebs instance first which could take many
    # hours due to EBS warm up, no reason to create other instance and wait.
    $TERRAFORM apply $VAR $VAR_FILE -var="mongod_ebs_instance_count=0" -var="workload_instance_count=0" | tee terraform.log

    # Create rest of the instanc when mongod_seeded_instance is created.
    $TERRAFORM apply $VAR $VAR_FILE | tee -a terraform.log
else
    # Most cluster types
    $TERRAFORM apply $VAR $VAR_FILE | tee terraform.log
fi
# repeat terraform apply to work around some timing issue between AWS/terraform
$TERRAFORM apply $VAR $VAR_FILE | tee -a terraform.log

$TERRAFORM refresh  $VAR $VAR_FILE
# Use terraform detailed exit code to catch terraform errors
$TERRAFORM plan -detailed-exitcode $VAR $VAR_FILE
if [[ $? != 0 ]]
then
    >&2 echo "Error: terraform plan -detailed-exitcode failed. Cluster not up"
    exit 1
fi

$TERRAFORM output | ${BINDIR}/generate_infrastructure.py
rc=$?
cat infrastructure_provisioning.out.yml

exit $rc

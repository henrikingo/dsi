#!/bin/bash

export CLUSTER=$1
export EXISTING="${2:-false}"
BINDIR=$(dirname $0)
TERRAFORM="${TERRAFORM:-./terraform}"

if [ ! "$CLUSTER" ]
then
    echo "Usage: $0 single|replica|shard|longevity|<cluster type>"
    exit -1
fi

$TERRAFORM get --update

$BINDIR/make_terraform_env.py --out-file cluster.json

VAR_FILE=""
if [ -e "cluster.json" ]; then
    VAR_FILE="-var-file=cluster.json"
    echo "Using var_file ${VAR_FILE}"
fi

echo "EXISTING IS $EXISTING"
if [ $EXISTING == "true" ]; then
    echo "Reusing AWS cluster for $CLUSTER"
else
    echo "Create AWS cluster for $CLUSTER"
fi

# create all resources and instances
if [[ $EXISTING != "true"  && ( $CLUSTER == "shard" || $CLUSTER == "longevity" ) ]]
then
    # Shard cluster
    $TERRAFORM apply $VAR_FILE -var="mongod_instance_count=3"  | tee terraform.log

    # workaround for failure to bring up all at the same time
    $TERRAFORM apply $VAR_FILE -var="mongod_instance_count=9" | tee -a terraform.log
else
    # Most cluster types
    $TERRAFORM apply $VAR_FILE | tee terraform.log
fi

# just to print out disk i/o information
cat terraform.log | grep "  clat ("

# Use rc 0 unless set otherwise
rc=0
if [ $CLUSTER == "longevity" ] || \
   [ $CLUSTER == "single-correctness" ] || \
   [ $CLUSTER == "replica-correctness" ]
then
    echo "Skipping pre-qualify-cluster.sh for $CLUSTER"
else
    # check performance and re-done the mongod instance if necessary
    ${BINDIR}/pre-qualify-cluster.sh
    rc=$?

    if [ $CLUSTER != "single" ] && [ $CLUSTER != "windows-single" ]
    then
        # disable system failure for the larger cluster types, as well as low end instance types
        if [[ $rc != 0 ]]
        then
            >&2 echo "Prequalify failed, but still running tests. There should be a functional"
            >&2 echo "cluster, but some of the nodes may have slow IO"
        fi
        rc=0
    fi
fi

# this will extract all public and private IP address information into a file ips.sh
${BINDIR}/env.sh

# Use the return code from pre-qualify-cluster.sh if there was one
if [[ $rc != 0 ]]
then
    >&2 echo "Error: Prequalify failed for setup-cluster.sh. Exiting and not running tests"
else
    # Check that all the nodes in the cluster are properly up
    good_line_count=$($TERRAFORM plan $VAR_FILE | egrep "Plan" | egrep -c "0 to add")
    if [ $good_line_count != 1 ]
    then
        >&2 echo "Error: Past pre-qualify, but something wrong with provisioning. Still need to add node(s)."
        $TERRAFORM $VAR_FILE plan
        rc=1
    fi
fi
exit $rc

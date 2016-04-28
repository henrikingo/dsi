#!/bin/bash

export CLUSTER=$1
BINDIR=$(dirname $0)
export TERRAFORM_DIR=${2:-${BINDIR}/../terraform}

if [ ! "$CLUSTER" ]
then
    echo "Usage: $0 single|replica|shard|longevity|<cluster type>"
    exit -1
fi

cp ${TERRAFORM_DIR}/* .

# create all resources and instances
if [ $CLUSTER == "shard" -o $CLUSTER == "longevity" ]
then
    # Shard cluster
    ./terraform apply -var="count=3"  | tee terraform.log

    # workaround for failure to bring up all at the same time
    ./terraform apply -var="count=9" | tee -a terraform.log
else
    # Most cluster types
    ./terraform apply  | tee terraform.log
fi

# just to print out disk i/o information
cat terraform.log | grep "  clat ("

if [ $CLUSTER == "longevity" ] || [ $CLUSTER == "single-correctness" ]
then
    echo "Skipping pre-qualify-cluster.sh for $CLUSTER"
else
    # check performance and re-done the mongod instance if necessary
    ${BINDIR}/pre-qualify-cluster.sh
    rc=$?

    if [ $CLUSTER != "single" ] && [ $CLUSTER != "windows-single" ]
    then
        # disable system failure for the larger cluster types, as well as low end instance types
        rc=0
    fi
fi

# this will extract all public and private IP address information into a file ips.sh
${BINDIR}/env.sh

# Use the return code from pre-qualify-cluster.sh if there was one
if [[ $rc != 0 ]]; then exit $rc; fi

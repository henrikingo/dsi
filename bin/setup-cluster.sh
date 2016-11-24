#!/bin/bash

export CLUSTER=$1
export EXISTING="${2:-false}"
SKIP_FIO=$3
BINDIR=$(dirname $0)
TERRAFORM="${TERRAFORM:-./terraform}"

if [ ! "$CLUSTER" ]
then
    echo "Usage: $0 single|replica|shard|longevity|<cluster type> [EXISTING=true|false] [--skip-fio]"
    exit -1
fi

$TERRAFORM get --update

$BINDIR/make_terraform_env.py --out-file cluster.json

VAR_FILE=""
if [ -e "cluster.json" ]; then
    VAR_FILE="-var-file=cluster.json"
    echo "Using var_file ${VAR_FILE}"
fi

VAR=""
if [ "$SKIP_FIO" == "--skip-fio" ]
then
    echo "Not running fio as specified by --skip-fio."
    VAR='-var run_fio=false'
    echo "Using -var option: $VAR"
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
    $TERRAFORM apply $VAR $VAR_FILE -var="mongod_instance_count=3"  | tee terraform.log

    # workaround for failure to bring up all at the same time
    $TERRAFORM apply $VAR $VAR_FILE -var="mongod_instance_count=9" | tee -a terraform.log
else
    # Most cluster types
    $TERRAFORM apply $VAR $VAR_FILE | tee terraform.log
fi
# repeat terraform apply to work around some timing issue between AWS/terraform
$TERRAFORM apply $VAR $VAR_FILE | tee -a terraform.log

# just to print out disk i/o information
cat terraform.log | grep "  clat ("

# Use rc 0 unless set otherwise
rc=0
if [ $CLUSTER == "longevity" ] || \
   [ $CLUSTER == "replica-initialsync_1tb" ] || \
   [ $CLUSTER == "single-correctness" ] || \
   [ $CLUSTER == "replica-correctness" ]
then
    echo "Skipping pre-qualify-cluster.sh for $CLUSTER"
elif [ "$SKIP_FIO" == "--skip-fio" ]
then
    echo "Skipping pre-qualify-cluster.sh because of --skip-fio."
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

# Use the return code from pre-qualify-cluster.sh if there was one
if [[ $rc != 0 ]]
then
    >&2 echo "Error: Prequalify failed for setup-cluster.sh. Exiting and not running tests"
else
    $TERRAFORM refresh
    # Use terraform detailed exit code to catch terraform errors
    $TERRAFORM plan -detailed-exitcode $VAR $VAR_FILE
    if [[ $? == 1 ]]
    then
        exit 1
    fi
    # Check that all the nodes in the cluster are properly up
    good_line_count=$($TERRAFORM plan $VAR $VAR_FILE | egrep "Plan" | egrep -c "0 to add")
    if [ $good_line_count != 1 ]
    then
        >&2 echo "Error: Past pre-qualify, but something wrong with provisioning. Still need to add node(s)."
        rc=1
    fi
fi

if [[ $rc == 0 ]]
then
    # this will extract all public and private IP address information into a file ips.sh
    # env.sh has to be called after the terraform pln check (see PERF-702 for details)
    ${BINDIR}/env.sh
    rc=$?
fi
exit $rc

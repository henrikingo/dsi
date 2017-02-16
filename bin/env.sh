#!/bin/bash

# explicity set the errexit so that we can catch conditions that
# terraform provisioning has failed
set -e

BINDIR=$(dirname $0)
TERRAFORM="${TERRAFORM:-./terraform}"

$TERRAFORM output public_all_host_ip  | awk '{for (i=1;i<=NF;i++) print("export+p",i,"=",$i)} {printf("export+ALL_HOST=(")}  {for (i=1;i<=NF;i++) printf("\"p%d\"+", i)} {print(")")}' | sed "s/ //g" | sed "s/+/ /g" | tee ips.sh
$TERRAFORM output private_all_host_ip  | awk '{for (i=1;i<=NF;i++) print("export+i",i,"=",$i)} {printf("export+ALL_HOST_PRIVATE=(")}  {for (i=1;i<=NF;i++) printf("i%d+", i)} {print(")")}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh
$TERRAFORM output public_ip_mc  | awk '{for (i=1;i<=NF;i++) print("export+mc","=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh

if [[ $CLUSTER == "shard" || $CLUSTER == "longevity" ]]
then
    # mongos
    $TERRAFORM output public_mongos_ip  | awk '{for (i=1;i<=NF;i++) print("export+ms","=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh
    $TERRAFORM output private_mongos_ip  | awk '{for (i=1;i<=NF;i++) print("export+ms_private_ip","=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh

    # number of shard
    $TERRAFORM output total_count  | awk '{for (i=1;i<=NF;i++) print("export+NUM_SHARDS","=",$i/3)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh
    $TERRAFORM output total_count  | awk '{for (i=1;i<=NF;i++) print("export+NUM_MONGOD","=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh

    # config server
    $TERRAFORM output public_config_ip  | awk '{for (i=1;i<=NF;i++) print("export+config",i,"=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee  -a ips.sh
    $TERRAFORM output private_config_ip  | awk '{for (i=1;i<=NF;i++) print("export+IPconfig",i,"=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh
fi

# yaml file copies over ips.py. Touch it so the copy doesn't fail
touch ips.py

# generate infrastructure_provisioning.out.yml
$TERRAFORM output | ${BINDIR}/generate_infrastructure.py
cat infrastructure_provisioning.out.yml

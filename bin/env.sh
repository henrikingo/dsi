#!/bin/bash

./terraform output public_member_ip  | awk '{for (i=1;i<=NF;i++) print("export+p",i,"=",$i)} {printf("export+ALL_HOST=(")}  {for (i=1;i<=NF;i++) printf("\"p%d\"+", i)} {print(")")}' | sed "s/ //g" | sed "s/+/ /g" | tee ips.sh
./terraform output private_member_ip  | awk '{for (i=1;i<=NF;i++) print("export+i",i,"=",$i)} {printf("export+ALL_HOST_PRIVATE=(")}  {for (i=1;i<=NF;i++) printf("i%d+", i)} {print(")")}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh
./terraform output public_ip_mc  | awk '{for (i=1;i<=NF;i++) print("export+mc","=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh

if [ $CLUSTER == "shard" -o $CLUSTER == "longevity" ]
then
# mongos
./terraform output public_mongos_ip  | awk '{for (i=1;i<=NF;i++) print("export+ms","=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh
./terraform output private_mongos_ip  | awk '{for (i=1;i<=NF;i++) print("export+ms_private_ip","=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh

# number of shard
./terraform output total_count  | awk '{for (i=1;i<=NF;i++) print("export+NUM_SHARDS","=",$i/3)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh
./terraform output total_count  | awk '{for (i=1;i<=NF;i++) print("export+NUM_MONGOD","=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh

# config server
./terraform output public_config_ip  | awk '{for (i=1;i<=NF;i++) print("export+config",i,"=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee  -a ips.sh
./terraform output private_config_ip  | awk '{for (i=1;i<=NF;i++) print("export+IPconfig",i,"=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh
fi

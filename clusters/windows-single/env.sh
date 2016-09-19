#!/bin/bash

TERRAFORM="${TERRAFORM:-../../terraform/terraform}"

$TERRAFORM output public_member_ip  | awk '{for (i=1;i<=NF;i++) print("export+p",i,"=",$i)} {printf("export+ALL_HOST=(")}  {for (i=1;i<=NF;i++) printf("\"p%d\"+", i)} {print(")")}' | sed "s/ //g" | sed "s/+/ /g" | tee ips.sh
$TERRAFORM output private_member_ip  | awk '{for (i=1;i<=NF;i++) print("export+i",i,"=",$i)} {printf("export+ALL_HOST_PRIVATE=(")}  {for (i=1;i<=NF;i++) printf("i%d+", i)} {print(")")}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh
$TERRAFORM output public_ip_mc  | awk '{for (i=1;i<=NF;i++) print("export+mc","=",$i)}' | sed "s/ //g" | sed "s/+/ /g" | tee -a ips.sh



#!/bin/bash

BINDIR=$(dirname $0)
source ${BINDIR}/config-replica-base.sh


startReplicaSet $version 0 $_storageEngine 3

# done
echo 
echo 
echo 

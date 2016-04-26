#!/bin/bash

if [[ $# -lt 2 ]]
then
    echo "Usage: $(basename $0) setup storageEngine"
    exit -1
fi

BINDIR=$(dirname $0)
setup=$1
storageEngine=$2

# Temporary hack: MongoDB config on Windows is a separate file, and was actively
# worked on while this refactoring was done. It will later be merged here.
# For now, just run the separate file when on Windows
isWindows=$(echo $(basename $(pwd)) | cut -c 1-7)
if [ "$isWindows" == "windows" ]
then
    $BINDIR/config-${setup}.sh "mongodb" $storageEngine
    exit $? # Return whatever that script returned
fi

source setting.sh
source ${BINDIR}/lib-configure-mongodb-basic.sh
source ${BINDIR}/lib-configure-mongodb-cluster.sh


if [ $setup == "standalone" ]
then
    startStandalone "mongodb" $p1 $storageEngine
elif [ $setup == "single-replica" ]
then
    startReplicaSet "mongodb" 0 $storageEngine 1
elif [ $setup == "replica" ]
then
    startReplicaSet "mongodb" 0 $storageEngine 3
elif [ $setup == "replica-2node" ]
then
    startReplicaSet "mongodb" 0 $storageEngine 2
elif [ $setup == "shard" ]
then
    startShardedCluster "mongodb" 0 $storageEngine 3 3
fi


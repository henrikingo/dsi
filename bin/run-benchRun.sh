#!/bin/bash

STORAGE_ENGINE=$1
CLUSTER=$3

BINDIR=$(dirname $0)
source setting.sh

# Bridging a historical inconsistency: prior to refactoring, the test name for
# MMAPv1 engine was "benchRun-mmap". However, the parameter ${storageEngine}
# has the value "mmapv1" (which is the name of the engine in mongod config).
if [ $STORAGE_ENGINE == "mmapv1" ]
then
    STORAGE_ENGINE="mmap"
fi

if [ $STORAGE_ENGINE != "wiredTiger" ]
then
    TEST="benchRun-$STORAGE_ENGINE"
else
    TEST="benchRun"
fi

cat ips.sh
cat run-$TEST.json
./update_run_config.sh
cat run-$TEST.json
rm -rf ./reports
rm -f ../../reports.tgz


# need make sure we checked out 10gen/workloads repo first
rm -rf ./workloads
rm -f workloads.tar.gz
git clone git@github.com:10gen/workloads.git
tar cvf workloads.tar ./workloads 
gzip workloads.tar

ssh -oStrictHostKeyChecking=no -T -A -i $PEMFILE $SSHUSER@$mc rm -rf workloads*

scp -oStrictHostKeyChecking=no -i $PEMFILE  ./workloads.tar.gz $SSHUSER@$mc:.

ssh -oStrictHostKeyChecking=no -T -i $PEMFILE $SSHUSER@$mc "tar zxvf workloads.tar.gz; pwd; ls workloads/*"

# also need get the proper mongo shell to run the test
# based on discussion, we will use bundle mongoshell, 
# which is already setup, so skip this for now until we 
# feel want to change the shell. 
# ssh -T -i $PEMFILE $SSHUSER@$mc  "rm -rf 3.1.7; rm -rf bin; mkdir -p 3.1.7; mkdir -p bin; curl https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-3.1.7.tgz | tar zxv -C 3.1.7; cd 3.1.7; mv */bin .; cd ../bin; ln -s ../3.1.7/bin/mongo mongo"

MC_MONITOR_INTERVAL=1 ${BINDIR}/mc -config run-$TEST.json -run $TEST-run -o perf.json

chmod 777 perf.json

# Run the initial sync tests if we are in a replica set
if [ $CLUSTER == "replica" ] 
then
    ${BINDIR}/configure-mongodb-cluster.sh replica-2node $1
    ${BINDIR}/run-initialSync.sh ${STORAGE_ENGINE} replica_2node ${CLUSTER}
fi

rm -f ../perf.json
chmod 766 perf.json
cp ./perf.json ..
pwd
cat ../perf.json

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
    TEST="ycsb-$STORAGE_ENGINE"
else
    TEST="ycsb"
fi

cat ips.sh
cat run-$TEST.json
./update_run_config.sh
cat run-$TEST.json
rm -rf ./reports
rm -f ../../reports.tgz

if [ $CLUSTER == "longevity" ]
then
    MC_PER_THREAD_STATS="no" MC_MONITOR_INTERVAL=10 ${BINDIR}/mc -config run-$TEST.json -run ycsb-run-longevity -o perf.json
else
    MC_MONITOR_INTERVAL=1 ${BINDIR}/mc -config run-$TEST.json -run $TEST-run -o perf.json
fi

rm -f ../perf.json
chmod 766 perf.json
cp ./perf.json ..
pwd
cat ../perf.json

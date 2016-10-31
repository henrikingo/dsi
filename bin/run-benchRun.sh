#!/bin/bash

set -e

STORAGE_ENGINE=$1
CLUSTER=$3

BINDIR=$(dirname $0)
source $BINDIR/setting.sh

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
rm -rf ./reports
rm -f ../../reports.tgz

source ${BINDIR}/setup-workloads.sh

# PERF-531. Generating config file for mission control.
python $BINDIR/config_test_control.py
echo "Generated mc.json"
scp -oStrictHostKeyChecking=no -i $PEMFILE  workloads.yml $SSHUSER@$mc:./workloads/

cat mc.json

MC=${MC:-"${BINDIR}/mc"}
MC_MONITOR_INTERVAL=1 $MC -config mc.json -run $TEST-run -o perf.json

chmod 777 perf.json

# Copy back over timestamp csv file
scp -oStrictHostKeyChecking=no -i $PEMFILE  $SSHUSER@$mc:./workloads/workload_timestamps.csv reports

rm -f ../perf.json
chmod 766 perf.json
cp ./perf.json ..
pwd
cat ../perf.json

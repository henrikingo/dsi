#!/bin/bash

STORAGE_ENGINE=$1
CLUSTER=$3

BINDIR=$(dirname $0)
source setting.sh

./update_run_config.sh
rm -rf ./reports
rm -f ../../reports.tgz

source ${BINDIR}/setup-workloads.sh

# Bridging a historical inconsistency: prior to refactoring, the test name for
# MMAPv1 engine was "benchRun-mmap". However, the parameter ${storageEngine}
# has the value "mmapv1" (which is the name of the engine in mongod config).
if [ $STORAGE_ENGINE == "mmapv1" ]
then
    STORAGE_ENGINE="mmap"
fi

function runInitialSyncTest {
    TEST_NAME=$1
    if [ $STORAGE_ENGINE != "wiredTiger" ]
    then
        TEST="$TEST_NAME-$STORAGE_ENGINE"
    else
        TEST="$TEST_NAME"
    fi

    # This should be updated to match run-benchRun.sh from PERF-531
    cp run-$TEST.json mc.json
    echo "Using run-$TEST.json as mc.json"

    MC_MONITOR_INTERVAL=1 ${BINDIR}/mc -config mc.json -run $TEST-run -o perf.json
}

declare -a arr=("initialSync_c_1_d_1_w_f" "initialSync_c_32_d_1_w_f" "initialSync_c_1_d_32_w_f" "initialSync_c_32_d_32_w_f" "initialSync_c_1_d_1_w_t" "initialSync_c_32_d_1_w_t" "initialSync_c_1_d_32_w_t" "initialSync_c_32_d_32_w_t" )
cp mongodb_setup.replica-2node.${STORAGE_ENGINE}.yml mongodb_setup.yml
for i in "${arr[@]}"
do
    cp mongodb_setup.replica-2node.${STORAGE_ENGINE}.yml mongodb_setup.yml
    python ${BINDIR}/mongodb_setup.py --config
    runInitialSyncTest $i
done

scp -oStrictHostKeyChecking=no -i $PEMFILE  $SSHUSER@$mc:./workloads/workload_timestamps.csv reports

rm -f ../perf.json
chmod 766 perf.json
cp ./perf.json ..
pwd
cat ../perf.json




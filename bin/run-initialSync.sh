#!/bin/bash

STORAGE_ENGINE=$1
CLUSTER=$3

BINDIR=$(dirname $0)
source $BINDIR/setting.sh

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
    MC=${MC:-"${BINDIR}/mc"}
    MC_MONITOR_INTERVAL=1 $MC -config mc.json -run $TEST-run -o perf.json
}

# Initial sync tests run multiple times, each with a different test
# list. This line copies the starting config file to a copy that will
# only be read. A succession of test_control.yml files will be made
# from it. 
cp test_control.yml test_control.initialSync.yml 

declare -a arr=("initialsync_c_1_d_1_w_f" "initialsync_c_32_d_1_w_f" "initialsync_c_1_d_32_w_f" "initialsync_c_32_d_32_w_f" "initialsync_c_1_d_1_w_t" "initialsync_c_32_d_1_w_t" "initialsync_c_1_d_32_w_t" "initialsync_c_32_d_32_w_t" )
for i in "${arr[@]}"
do
    python ${BINDIR}/mongodb_setup.py --config

    # update the test control for each iteration through the loop and
    # keep a copy of each config file that is used.

    # Note that this code exists because our infrastructure cannot
    # reset or reconfigure the cluster between test runs. If it could,
    # this whole loop would not be needed and this file could be
    # collapsed with run-benchRun.sh, or removed.
    # See https://jira.mongodb.org/browse/PERF-562

    python ${BINDIR}/update_test_list.py $i --input-file test_control.initialSync.yml --output-file test_control.yml
    # Keep a copy of this file.
    cp test_control.yml test_control.${i}.yml
    python $BINDIR/config_test_control.py
    echo "Generated mc.json"
    cat mc.json
    scp -oStrictHostKeyChecking=no -i $PEMFILE  workloads.yml $SSHUSER@$mc:./workloads/
    runInitialSyncTest $i
done

scp -oStrictHostKeyChecking=no -i $PEMFILE  $SSHUSER@$mc:./workloads/workload_timestamps.csv reports

rm -f ../perf.json
chmod 766 perf.json
cp ./perf.json ..
pwd
cat ../perf.json

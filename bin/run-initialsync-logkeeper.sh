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

# Prepare workload for background traffic
# This should be moved into test_control YML file once PERF-436 is fixed.
# In order to run mongoreplay build we are using, we need download and extract the traffic dump file
# and get the proper version of libpcap.so. The current mongoreplay build is from 
# https://evergreen.mongodb.com/version/5849d9903ff122540a007a70
# We should move to upstream once all fixes are committed.
ssh -oStrictHostKeyChecking=no -i $PEMFILE $SSHUSER@$mc << EOF
curl -O --retry 10 https://s3.amazonaws.com/mciuploads/mongo-tools/binaries/mongo_tools_ubuntu_b3187697d342563efd9b90bdd1aa574aec4d2e00_16_12_08_22_07_30/community/mongoreplay
chmod +x mongoreplay
curl -o /media/ephemeral0/initialsync.playback.tgz --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/initialsync.playback.tgz
curl -o /media/ephemeral0/libpcap.so.0.8  --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/libpcap/libpcap.so.0.8
cd /media/ephemeral0
tar zxvf initialsync.playback.tgz
exit
EOF

cat mc.json

MC=${MC:-"${BINDIR}/mc"}
MC_MONITOR_INTERVAL=60 $MC -config mc.json -run $TEST-run -o perf.json

# We have to kill mongoreplay, this is not the ideal location for this. The proper fix should be
# in mission-control, there is a defer command to kill background tasks, which is not executed
# properly. See here for details on how to fix it:
# http://stackoverflow.com/questions/27629380/how-to-exit-a-go-program-honoring-deferred-calls
ssh -oStrictHostKeyChecking=no -i $PEMFILE $SSHUSER@$mc << EOF
killall -9 mongoreplay
killall -9 mongoreplay
exit
EOF

chmod 777 perf.json

# Copy back over timestamp csv file
scp -oStrictHostKeyChecking=no -i $PEMFILE  $SSHUSER@$mc:./workloads/workload_timestamps.csv reports

rm -f ../perf.json
chmod 766 perf.json
cp ./perf.json ..
pwd
cat ../perf.json

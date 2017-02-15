#!/bin/bash

set -e

STORAGE_ENGINE=$1
CLUSTER=$3

BINDIR=$(dirname $0)
source $BINDIR/setting.sh

eval `ssh-agent -s`
ssh-add $PEMFILE

# Bridging a historical inconsistency: prior to refactoring, the test name for
# MMAPv1 engine was "ycsb-mmap". However, the parameter ${storageEngine}
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

export DSI_PATH=${DSI_PATH:-${BINDIR}/..}
export YCSB_DIR=${YCSB_DIR:-${DSI_PATH}/../../YCSB/YCSB}
echo DSI PATH is $DSI_PATH
echo YCSB_DIR is $YCSB_DIR

# Use ycsb checkedout by module if it exists. Need to use relative
# path because in Evergreen source is checked out into a unique
# (random) absolute path.
if [ ! -e ${YCSB_DIR} ]
then
    # need make sure we checked out mongodb-labs/ycsb repo first
    echo ycsb dir does not exist
    rm -rf ./YCSB
    rm -f ycsb.tar.gz
    git clone -b evergreen https://github.com/mongodb-labs/YCSB.git
    YCSB_DIR=./YCSB
fi

echo "Using ycsb in $YCSB_DIR"
# Make a clean tarball of ycsb. Delete an existing one
if [ -e ycsb.tar.gz ]
then
    rm ycsb.tar.gz
fi

tar -cvf ycsb.tar --exclude=.git* -C $(dirname $YCSB_DIR) $(basename $YCSB_DIR)
gzip ycsb.tar

ssh -oStrictHostKeyChecking=no -T -A -i $PEMFILE $SSHUSER@$mc rm -rf ycsb*

scp -oStrictHostKeyChecking=no -i $PEMFILE  ./ycsb.tar.gz $SSHUSER@$mc:.

ssh -oStrictHostKeyChecking=no -T -i $PEMFILE $SSHUSER@$mc "tar zxvf ycsb.tar.gz; pwd; ls YCSB/*; source /etc/profile.d/maven.sh; cd /home/ec2-user/YCSB/ycsb-mongodb || exit 1; ./setup.sh"

# Copy up helper script
scp -oStrictHostKeyChecking=no -i $PEMFILE $BINDIR/process_fio_results.py $SSHUSER@$mc:./
scp -oStrictHostKeyChecking=no -i $PEMFILE $BINDIR/fio-test.sh $SSHUSER@$mc:./
ssh -oStrictHostKeyChecking=no -T -A -i $PEMFILE $SSHUSER@$mc chmod 755 fio-test.sh

cat ips.sh
rm -rf ./reports
rm -f ../../reports.tgz

# PERF-531. Generating config file for mission control.
python $BINDIR/config_test_control.py
echo "Generated mc.json"

if [ -e fio.ini ]; then
   scp -oStrictHostKeyChecking=no -i $PEMFILE  fio.ini $SSHUSER@$mc:./
fi

cat mc.json

MC=${MC:-"${BINDIR}/mc"}
if [ $CLUSTER == "longevity" ]
then
    MC_PER_THREAD_STATS="no" MC_MONITOR_INTERVAL=10 $MC -config mc.json -run ycsb-run-longevity -o perf.json
else
    MC_MONITOR_INTERVAL=1 $MC -config mc.json -run $TEST-run -o perf.json
fi

# Copy back over fio output file if it exists
scp -oStrictHostKeyChecking=no -i $PEMFILE  $SSHUSER@$mc:./fio.json reports || true
scp -oStrictHostKeyChecking=no -i $PEMFILE  $SSHUSER@$mc:./fio.json.[0-9] reports || true
scp -oStrictHostKeyChecking=no -i $PEMFILE  $SSHUSER@$mc:./fio.json.p.[0-9] reports || true


rm -f ../perf.json
chmod 766 perf.json
cp ./perf.json ..
pwd
cat ../perf.json

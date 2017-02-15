#!/bin/bash

BINDIR=$(dirname $0)
export DSI_PATH=${DSI_PATH:-${BINDIR}/..}
export WORKLOADS_DIR=${WORKLOADS_DIR:-${DSI_PATH}/../../workloads/workloads}
echo DSI PATH is $DSI_PATH
echo WORKLOADS_DIR is $WORKLOADS_DIR

# Use workloads checkedout by module if it exists. Need to use
# relative path because in Evergreen source is checked out into a
# unique (random) absolute path.
if [ ! -e ${WORKLOADS_DIR} ]
then
    # need make sure we checked out 10gen/workloads repo first
    echo workloads dir does not exist
    rm -rf ./workloads
    rm -f workloads.tar.gz
    git clone git@github.com:10gen/workloads.git
    WORKLOADS_DIR=./workloads
fi
echo "Using workloads in $WORKLOADS_DIR"

# Make a clean tarball of workloads. Delete an existing one
if [ -e workloads.tar.gz ]
then
    rm workloads.tar.gz
fi

tar -cvf workloads.tar --exclude=.git* -C $(dirname $WORKLOADS_DIR) $(basename $WORKLOADS_DIR)
gzip workloads.tar

ssh -oStrictHostKeyChecking=no -T -A -i $PEMFILE $SSHUSER@$mc rm -rf workloads*

scp -oStrictHostKeyChecking=no -i $PEMFILE  ./workloads.tar.gz $SSHUSER@$mc:.

ssh -oStrictHostKeyChecking=no -T -i $PEMFILE $SSHUSER@$mc "tar zxvf workloads.tar.gz; pwd; ls workloads/*"

# Copy up helper script
scp -oStrictHostKeyChecking=no -i $PEMFILE $BINDIR/process_fio_results.py $SSHUSER@$mc:./
scp -oStrictHostKeyChecking=no -i $PEMFILE $BINDIR/fio-test.sh $SSHUSER@$mc:./
ssh -oStrictHostKeyChecking=no -T -A -i $PEMFILE $SSHUSER@$mc chmod 755 fio-test.sh

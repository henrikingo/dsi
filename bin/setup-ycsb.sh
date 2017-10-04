#!/bin/bash

set -e

BINDIR=$(dirname $0)
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
    # Checkout done in a subshell to protect CWD
    (rm -rf ./YCSB
    rm -f ycsb.tar.gz
    git clone https://github.com/mongodb-labs/YCSB.git
    cd YCSB
    git checkout 5742781
    )
    YCSB_DIR=./YCSB
fi

echo "Using ycsb in $YCSB_DIR"
# Make a clean tarball of ycsb. Delete an existing one
if [ -e ycsb.tar.gz ]
then
    rm ycsb.tar.gz
fi

tar -czvf ycsb.tar.gz --exclude=.git* -C $YCSB_DIR .
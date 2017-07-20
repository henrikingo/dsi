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

if [ -x "$WORKLOADS_DIR/jsdoc/generate.sh" ]
then
    PATH="/opt/node/bin:$PATH"
    if ! hash jsdoc 2>/dev/null ; then
        echo "jsdoc not installed"
        /opt/node/bin/npm install -g jsdoc
    fi
    $WORKLOADS_DIR/jsdoc/generate.sh
else
    echo "$WORKLOADS_DIR/jsdoc/generate.sh missing or not executable"
fi

tar -czvf workloads.tar.gz --exclude=.git* -C $WORKLOADS_DIR .


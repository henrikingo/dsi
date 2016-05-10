#!/bin/bash

cp terraform.log post-check.log
REDO_INSTANCE=false
DIR=$(dirname "$0")

# This will check for all "bad" intance, mark them as tainted
# and then re-create them, total will try 5 times. If there
# is still bad instance at the end, will fail test with system error
for j in $(seq 5)
do
    REDO_INSTANCE=false

    # print into log
    grep " clat (" post-check.log
    for i in $(grep " clat (" post-check.log | $DIR/filter_bad_instance.py )
    do
        ./terraform taint "$i"
        echo "Recreate instance $i"
        REDO_INSTANCE=true
    done

    if $REDO_INSTANCE; then
        ./terraform apply | tee post-check.log
    fi
done

if $REDO_INSTANCE; then
    >&2 echo "Error: still have tainted instance after 5 tries, exit tests" 
    exit 1
fi


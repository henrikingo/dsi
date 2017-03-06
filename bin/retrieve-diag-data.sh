#!/bin/bash

source $(dirname $0)/utils.bash

# retrieve FTDC and organize them based on name

readonly FILES=( "data/dbs/diagnostic.data" "data/logs/mongo*.log")

mkdir -p reports

for i in "${ALL_HOST[@]}"
do
    echo "Retrieve diag data from mongod ${i}:${!i}"
    mkdir -p reports/diag-$i-${!i}

    for f in "${FILES[@]}"
    do
        scpFile ${!i} $f reports/diag-$i-${!i}/
    done
done

# For sharded variants, also collect log data for mongos and config servers
if [ "$ms" != "" ]
then
    echo "Retrieve diag data from mongos: $ms"
    mkdir -p reports/diag-mongos-$ms
    # No diagnostic.data on mongos
    scpFile $ms "data/logs/mongo*.log" reports/diag-mongos-$ms/ || true

    for c in $config1 $config2 $config3
    do
        echo "Retrieve diag data from config server: $c"
        mkdir -p reports/diag-config-$c
        for f in "${FILES[@]}"
        do
            scpFile $c $f reports/diag-config-$c/ || true
        done
    done
fi

echo "Done save diag data"

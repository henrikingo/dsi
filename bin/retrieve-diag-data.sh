#!/bin/bash

source $(dirname $0)/utils.bash

# retrieve FTDC and organize them based on name

readonly FILES=( "data/dbs/diagnostic.data" )

mkdir -p reports

for i in "${ALL_HOST[@]}"
do
    echo "Retrieve diag data from ${i}:${!i}"
    mkdir -p reports/diag-$i-${!i}

    for f in "${FILES[@]}"
    do
        scpFile ${!i} $f reports/diag-$i-${!i}/
    done
done

echo "Done save diag data"

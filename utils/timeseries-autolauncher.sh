#!/bin/bash

# A helper to launch timeseries.py once for every diagnostics.data stored
# in this reports.tgz.
# Note: This script is intended to be copied into and run from inside 
# the reports.tgz. It will do nothing if run from a dsi repo.

cd $(dirname $0)

PORT=8889

echo "Launching timeseries.py $NUM_MONGOD times, once for each diagnostics.data/ in"
echo "this archive. You can browse the graphs interactively in the chrome tabs that open."
echo
echo

virtualenv ./venv
source ./venv/bin/activate
pip install argparse python-dateutil pytz

# list all the top level directories matching the patterns
DIRECTORIES=( $(find . -maxdepth 1 -name 'mongo*' -o -name 'config*' -type d ) )
for directory in "${DIRECTORIES[@]}"
do
    name=$(basename ${directory})  # get the leaf level directory name

    # iostat logs are not available on Windows
    iostat_log=$(compgen -G "${name}/iostat.log*")

    # Include timestamp information from workloads if it exists
    timestamps=""
    if [ -e workload_timestamps.csv ]
    then
        timestamps="workload_timestamps.csv"
    fi

    python $(dirname $0)/timeseries.py --itz 0 --port $PORT \
                                       ${name}/diagnostic.data \
                                       ${name}/mongod.log $iostat_log \
                                       $timestamps
    PORT=$(($PORT+1))
done


#!/bin/bash

# A helper to launch timeseries.py once for every diagnostics.data stored
# in this reports.tgz.
# Note: This script is intended to be copied into and run from inside 
# the reports.tgz. It will do nothing if run from a dsi repo.

cd $(dirname $0)
IPS=ips.sh

if [ ! -f $IPS ]
then
    echo "This script is intended to be run from inside a reports.tgz archive."
    echo "This does not appear to be a reports.tgz archive directory. No $IPS file found."
    exit
fi

source $IPS
PORT=8889

echo "Launching timeseries.py $NUM_MONGOD times, once for each diagnostics.data/ in"
echo "this archive. You can browse the graphs interactively in the chrome tabs that open."
echo
echo

virtualenv ./venv
source ./venv/bin/activate
pip install argparse python-dateutil pytz

for i in "${ALL_HOST[@]}"
do
    # iostat logs are not available on Windows
    iostat_log=""
    if [ -e */*/iostat.log--ec2-user@${!i} ]
    then
       iostat_log=$(ls */*/iostat.log--ec2-user@${!i})
    fi

    # Include timestamp information from workloads if it exists
    timestamps=""
    if [ -e workload_timestamps.csv ]
    then
        timestamps="workload_timestamps.csv"
    fi

    python $(dirname $0)/timeseries.py --itz 0 --port $PORT \
                                       diag-$i-${!i}/diagnostic.data \
                                       diag-$i-${!i}/mongod.log $iostat_log \
                                       $timestamps
    PORT=$(($PORT+1))
done


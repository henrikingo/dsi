#!/bin/bash

echo Generate timeseries graphs from FTDC, mongod.log and iostat data.

echo Install python modules needed by timeseries.py into a python virtualenv.
python --version
virtualenv ./venv
source ./venv/bin/activate
pip install argparse python-dateutil pytz

echo Generate one html file for each host in cluster.
mkdir -p reports/graphs
# only list all the directories matching the pattern and ignoring errors / warnings
DIRECTORIES=( $(find reports -maxdepth 1 -name 'mongo*' -o -name 'config*' -type d ) )
for directory in "${DIRECTORIES[@]}"
do
    name=$(basename ${directory}) # get the leaf level directory name

    # iostat logs are not available on Windows
    iostat_log=$(compgen -G "reports/${name}/iostat.log*")

    # Include timestamp information from workloads if it exists
    timestamps=""
    if [ -e reports/workload_timestamps.csv ]
    then
        timestamps="reports/workload_timestamps.csv"
    fi

    python $(dirname $0)/timeseries.py --itz 0 --overview all \
           reports/${name}/diagnostic.data \
           reports/${name}/mongod.log $iostat_log \
           $timestamps \
           --html reports/graphs/timeseries-${name}.html
done

echo
echo "Done with generating timeseries html files."
echo "For your convenience, I will also copy the timeseries.py into the tar file."
echo "It can be launched as a webserver to interactively zoom into the timeseries data."
echo "Just run timeseries-autolauncher.sh and it will open graphs in Chrome for you."
echo

cp $(dirname $0)/timeseries.py reports/
cp $(dirname $0)/../utils/timeseries-autolauncher.sh reports/

#!/bin/bash

source $(dirname $0)/utils.bash

source reports/ips.sh

echo Generate timeseries graphs from FTDC, mongod.log and iostat data.

echo Install python modules needed by timeseries.py into a python virtualenv.
python --version
virtualenv ./venv
source ./venv/bin/activate
pip install argparse python-dateutil pytz

echo Generate one html file for each host in cluster.
mkdir -p reports/graphs
for i in "${ALL_HOST[@]}"
do
    # iostat logs are not available on Windows
    iostat_log=""
    if [ -e reports/*/*/iostat.log--ec2-user@${!i} ]
    then
       iostat_log=$(ls reports/*/*/iostat.log--ec2-user@${!i})
    fi

    # Include timestamp information from workloads if it exists
    timestamps=""
    if [ -e reports/workload_timestamps.csv ]
    then
        timestamps="reports/workload_timestamps.csv"
    fi

    python $(dirname $0)/timeseries.py --itz 0 --overview all \
                                       reports/diag-$i-${!i}/diagnostic.data \
                                       reports/diag-$i-${!i}/mongod.log $iostat_log \
                                       $timestamps \
                                       --html reports/graphs/timeseries-$i.html
done

echo
echo "Done with generating timeseries html files."
echo "For your convenience, I will also copy the timeseries.py into the tar file."
echo "It can be launched as a webserver to interactively zoom into the timeseries data."
echo "Just run timeseries-autolauncher.sh and it will open graphs in Chrome for you."
echo

cp $(dirname $0)/timeseries.py reports/
cp $(dirname $0)/../utils/timeseries-autolauncher.sh reports/

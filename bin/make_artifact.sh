#!/bin/bash

# Make the test log artifact. Assumes it is run in the working
# directory This script only runs if there is no reports.tgz file. The
# script can safely be run repeatedly.

set -o verbose
source ./dsienv.sh
if [ -e reports.tgz ]; then
    echo "Reports.tgz already exists. Not generating"
else
    mkdir -p ./reports/graphs
    cd reports
    # move additional file here
    cp ../infrastructure_provisioning.out.yml .
    if [ -f "../terraform.log" ]; then cp ../terraform.log .; fi
    cp ../perf.json .
    cd ..
    touch ./reports/graphs/timeseries-p1.html
    $DSI_PATH/bin/retrieve-diag-data.sh
    $DSI_PATH/bin/generate-timeseries-html.sh || true
    tar -zvcf reports.tgz reports
fi

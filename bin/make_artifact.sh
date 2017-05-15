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
    cp ../bootstrap.yml .
    cp ../runtime.yml .

    if [ -f "../terraform.log" ]; then cp ../terraform.log .; fi
    cp ../perf.json .
    cd ..
    touch ./reports/graphs/timeseries-p1.html

    $DSI_PATH/bin/generate-timeseries-html.sh || true
    cp ./reports/graphs/timeseries-mongod.0.html ./reports/graphs/timeseries-p1.html


    # The long term plan is to tar the complete work directory, and
    # upload it. Currently we only save the reports directory. It is
    # very important to not include the following files when we save
    # the complete work directory:
    #
    # runtime_secret.yml
    # security.tf
    # aws_ssh_key.pem.
    #
    # Those files may be required after the end of this script. If
    # they are deleted for the call to tar, they need to be restored
    # afterwards. Alternatively, we can use the --exclude flag to tar. Can use the following string:
    # TAR_EXCLUDE="--exclude runtime_secret.yml --exclude security.tf --exclude aws_ssh_key.pem"

    tar -zvcf reports.tgz reports
fi

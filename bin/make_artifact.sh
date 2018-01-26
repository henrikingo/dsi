#!/bin/bash

# Make the test log artifact. Assumes it is run in the working
# directory. If dsi-artifacts.tgz already exists, will delete and recreate.

source ./dsienv.sh

# Exclude security sensitive files
TAR_EXCLUDE="--exclude runtime_secret.yml --exclude security.tf --exclude aws_ssh_key.pem"

TAR_ARTIFACT=dsi-artifacts.tgz
echo "Creating $TAR_ARTIFACT"
rm $TAR_ARTIFACT >/dev/null 2>&1 || true
tar $TAR_EXCLUDE --exclude reports.tgz -zcf $TAR_ARTIFACT *



# Kept for system_perf.yml backward compatibility (SERVER-32896). Safe to remove after 4.0 release.
if [ -e reports.tgz ]; then
    echo "Reports.tgz already exists. Not generating"
else
    mkdir -p ./reports
    cd reports
    # move additional file here
    cp ../infrastructure_provisioning.out.yml . || true
    cp ../bootstrap.yml . || true
    cp ../runtime.yml . || true

    if [ -f "../terraform.log" ]; then cp ../terraform.log .; fi
    cp ../perf.json . || true
    cd ..

    tar -hzcf reports.tgz reports
fi

#!/usr/bin/env bash

# Make the test log artifact. Assumes it is run in the working directory. If dsi-artifacts.tgz
# already exists, will delete and recreate

# fail whole script for undefined vars or any command failure
set -eou pipefail

source ./dsienv.sh

# Exclude security-sensitive and unnecessary files
TAR_EXCLUDE=""
TAR_EXCLUDE="$TAR_EXCLUDE --exclude runtime_secret.yml --exclude security.tf --exclude aws_ssh_key.pem"
TAR_EXCLUDE="$TAR_EXCLUDE --exclude venv --exclude reports.tgz"

TAR_ARTIFACT="dsi-artifacts.tgz"

echo "Creating $TAR_ARTIFACT"

rm "$TAR_ARTIFACT" >/dev/null 2>&1 || true
tar $TAR_EXCLUDE -zcf "$TAR_ARTIFACT" ./*

# Kept for system_perf.yml backward compatibility (SERVER-32896). Safe to remove after 4.0 release.
if [ -e reports.tgz ]; then
    echo "Reports.tgz already exists. Not generating"
else
    mkdir -p ./reports
    # move additional file here
    cp infrastructure_provisioning.out.yml ./reports || true
    cp bootstrap.yml                       ./reports || true
    cp runtime.yml                         ./reports || true
    cp perf.json                           ./reports || true

    if [ -f "terraform.log" ]; then
        cp terraform.log ./reports
    fi

    tar -hzcf reports.tgz reports
fi

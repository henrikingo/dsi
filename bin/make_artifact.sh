#!/usr/bin/env bash

# Make the test log artifact. Assumes it is run in the working directory. If dsi-artifacts.tgz
# already exists, will delete and recreate

# fail whole script for undefined vars or any command failure
set -eou pipefail

# Exclude security-sensitive and unnecessary files
EXCLUDED_FILES=(
    "aws_ssh_key.pem"
    "expansions.yml"
    "reports.tgz"
    "runtime_secret.yml"
    "security.tf"
    "venv"
)

TAR_EXCLUDE=""
for EXCLUDED_FILE in "${EXCLUDED_FILES[@]}"; do
    TAR_EXCLUDE+=" --exclude ${EXCLUDED_FILE}"
done

TAR_ARTIFACT="dsi-artifacts.tgz"
echo "Creating $TAR_ARTIFACT"
rm "$TAR_ARTIFACT" >/dev/null 2>&1 || true
tar $TAR_EXCLUDE -zcf "$TAR_ARTIFACT" ./*

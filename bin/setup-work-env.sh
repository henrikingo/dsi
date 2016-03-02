#!/bin/bash

# Setup an out of source work environment. Copy over the appropriate files.

# help function
function HELP() {
    printf "Usage: $(basename $0)\n"
    printf "  -c cluster type to setup. Default single\n"
    printf "  -m mongo url to download and install\n"
    printf "  -k keyname\n"
    printf "  -p keyfile path\n"
    printf "  -r region\n"
    printf "  -h print help message \n"

    exit 0
}

CLUSTER="single"
MONGO_URL="https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-amazon-3.2.3.tgz"
KEYNAME="Your keyname"
KEYFILEPATH="PATH TO YOUR KEYFILE"
REGION="us-west-2"

while getopts 'c:k:p:r:m:h' flag; do
    case "${flag}" in
        c) CLUSTER="${OPTARG}"; echo "Cluster type is: ${OPTARG}";;
        k) KEYNAME="${OPTARG}"; echo "Setting keyname: ${OPTARG}";;
        p) KEYFILEPATH="${OPTARG}"; echo "Setting keyfile: ${OPTARG}";;
        r) REGION="${OPTARG}"; echo "Setting region: ${OPTARG}";;
        m) MONGO_URL="${OPTARG}"; echo "Mongo URL: ${OPTARG}";;
        h) HELP ;;
    esac
done


# First sanity check -- do any of the files exist?
if [ -e dsienv.sh ]; then
    echo "It looks like you have already setup this directory. Stopping."
    echo "Delete dsienv.sh to run this program"
    exit;
fi

# Get current path
# Compute DSI_PATH from it.
# export DSI_PATH
# Write out bash script to set DSI_PATH
DIR=$(dirname $0)
echo $DIR
# This gets an absolute path to the DSI directory.
DSI_PATH=$(cd $(dirname $DIR) && pwd)
echo "export DSI_PATH=$DSI_PATH" > dsienv.sh


# Copy over a cluster config file
cp ${DSI_PATH}/clusters/${CLUSTER}/cluster.tf .
cp ${DSI_PATH}/clusters/${CLUSTER}/terraform.tfvars .
# cluster.tf and terraform.tfvars

# This is cut and pasted from make_terraform_env.sh
# replace the mongodb url with the proper build URL
sed -i -- "s#%%MONGO_URL%%#${3}#g" cluster.tf
sed -i -- "s#%%MONGO_URL%%#${3}#g" terraform.tfvars

echo "
provider \"aws\" {
    access_key = \"Fill in KEY\"
    secret_key = \"Fill in secret\"
    region = \"$REGION\"
}


variable \"key_name\" {
    default = \"${KEYNAME}\"
}

variable \"key_path\" {
    default = \"$KEYFILEPATH\"
}" > security.tf


# Prompt the user to edit it.
echo "Local environment setup"
echo "Please review/edit security.tf, cluster.tf, and terraform.tfvars for your setup, before continuing deployment"

#!/bin/bash

BINDIR=$(dirname $0)
source setting.sh

echo "Create terraform config file"

REGION="us-west-2"

if [ -f aws-region ]
then
    REGION=$(cat aws-region)
fi

echo "
provider \"aws\" {
    access_key = \"${1}\"
    secret_key = \"${2}\"
    region = \"${REGION}\"
}


variable \"key_name\" {
    default = \"rui-aws-cap\"
}

variable \"key_path\" {
    default = \"${PEMFILE}\"
}" > security.tf

# This is where we can call to setup terraform environment, it will also remove the above two
# lines for sed update for mongo URL.
# Here user and system can replace any default values for the production cluster
# eg.  python $BINDIR/make_terraform_env.py --config-file CONFIGURATION.YML --out-file cluster.json

# this will update expire-on tag only
python2.7 $BINDIR/make_terraform_env.py --out-file cluster.json

# update terraform module
./terraform get --update

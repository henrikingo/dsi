#!/bin/bash

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
    region = \"$REGION\"
}


variable \"key_name\" {
    default = \"rui-aws-cap\"
}

variable \"key_path\" { 
    default = \"../../keys/aws.pem\"
}" > security.tf

# replace the mongodb url with the proper build URL

sed -i -- "s#%%MONGO_URL%%#${3}#g" cluster.tf
sed -i -- "s#%%MONGO_URL%%#${3}#g" terraform.tfvars

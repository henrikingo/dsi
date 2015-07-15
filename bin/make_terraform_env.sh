#!/bin/bash

echo "Create terraform config file"

echo "
provider \"aws\" {
    access_key = \"${1}\"
    secret_key = \"${2}\"
    region = \"us-west-2\"
}


variable \"key_name\" {
    default = \"rui-aws-cap\"
}

variable \"key_path\" { 
    default = \"../../keys/aws.pem\"
}" > security.tf

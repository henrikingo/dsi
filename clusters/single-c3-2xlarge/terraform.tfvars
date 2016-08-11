key_name                = "rui-aws-cap"
key_file                = "../../../keys/aws.pem"
mongod_instance_count   = "1"
workload_instance_count = "1"

owner       = "rui.zhang"

mongod_instance_type    = "c3.2xlarge"
workload_instance_type  = "c3.2xlarge"
topology                = "single-c3-2xlarge"
availability_zone       = "us-west-2a"
region                  = "us-west-2"

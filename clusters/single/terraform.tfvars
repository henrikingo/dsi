key_name                = "rui-aws-cap"
key_file                = "../../../keys/aws.pem"
mongod_instance_count   = "1"
workload_instance_count = "1"

owner       = "rui.zhang"

workload_instance_type  = "c3.8xlarge"
mongod_instance_type    = "c3.8xlarge"
topology                = "single"
availability_zone       = "us-west-2a"
region                  = "us-west-2"

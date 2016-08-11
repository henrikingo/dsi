key_name                = "rui-aws-cap"
key_file                = "../../../keys/aws.pem"
mongod_instance_count   = "1"
workload_instance_count = "1"

owner       = "rui.zhang"

mongod_instance_type    = "m3.xlarge"
workload_instance_type  = "m3.xlarge"
topology                = "single-correctness"
availability_zone       = "us-east-1a"
region                  = "us-east-1"

workload_instance_placement_group   = "no"
mongod_instance_placement_group     = "no"

key_name                = "rui-aws-cap"
key_file                = "../../../keys/aws.pem"
mongod_instance_count   = "3"
workload_instance_count = "1"

mongourl    = "%%MONGO_URL%%"
owner       = "rui.zhang"

workload_instance_type  = "m3.xlarge"
mongod_instance_type    = "m3.xlarge"
topology                = "replica-correctness"
availability_zone       = "us-east-1a"
region                  = "us-east-1"

workload_instance_placement_group   = "no"
mongod_instance_placement_group     = "no"

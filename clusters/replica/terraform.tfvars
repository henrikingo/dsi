key_name                = "rui-aws-cap"
key_file                = "../../../keys/aws.pem"
mongod_instance_count   = "3"
workload_instance_count = "1"

mongourl    = "%%MONGO_URL%%"
owner       = "rui.zhang"

workload_instance_type  = "c3.8xlarge"
mongod_instance_type    = "c3.8xlarge"
topology                = "replica"
availability_zone       = "us-east-1a"
region                  = "us-east-1"

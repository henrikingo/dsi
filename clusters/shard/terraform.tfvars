key_name                    = "rui-aws-cap"
key_file                    = "../../../keys/aws.pem"
mongod_instance_count       = "9"
mongos_instance_count       = "1"
configserver_instance_count = "3"
workload_instance_count     = "1"


owner       = "rui.zhang"

workload_instance_type      = "c3.8xlarge"
mongod_instance_type        = "c3.8xlarge"
mongos_instance_type        = "c3.8xlarge"
configserver_instance_type  = "m3.xlarge"
topology                    = "shard"
availability_zone           = "us-west-2a"
region                      = "us-west-2"

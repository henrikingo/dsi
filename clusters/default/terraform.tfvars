key_name                = "rui-aws-cap"
key_file                = "../../keys/aws.pem"

# mongod instances
mongod_instance_count               = "0"
mongod_ebs_instance_count           = "0"
mongod_seeded_ebs_instance_count    = "0"

workload_instance_count             = "0"

owner       = "serverteam-perf@10gen.com"

workload_instance_type          = "c3.8xlarge"
mongod_instance_type            = "c3.8xlarge"
mongod_ebs_instance_type        = "c3.8xlarge"
mongod_seeded_ebs_instance_type = "c3.8xlarge"
topology                        = "default"
availability_zone               = "us-east-1a"
region                          = "us-east-1"

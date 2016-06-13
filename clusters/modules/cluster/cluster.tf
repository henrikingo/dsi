variable mongourl                       {}
variable owner                          {}
variable topology                       {}

# define instance types
variable mongod_instance_type           {}
variable mongos_instance_type           { default = "c3.4xlarge" }
variable workload_instance_type         {}
variable configserver_instance_type     { default = "m3.2xlarge" }

# define instance count
variable mongod_instance_count          { default = 0 }
variable mongos_instance_count          { default = 0 }
variable workload_instance_count        { default = 0 }
variable configserver_instance_count    { default = 0 }

# define whether to use placement_group
variable mongod_instance_placement_group        { default="yes" }
variable mongos_instance_placement_group        { default="yes" }
variable workload_instance_placement_group      { default="yes" }
variable configserver_instance_placement_group  { default="no" }

# AWS details
variable region                         {}
variable availability_zone              {}
variable key_path                       {}
variable key_name                       {}

variable expire_on                      { default = "2016-12-31" }

# define VPC and related network resources
module "VPC" {
    source = "../vpc"

    # parameter for module
    topology            = "${var.topology}"
    availability_zone   = "${var.availability_zone}"
    owner               = "${var.owner}"
}

# AWS instance with placement group for mongod
module "mongod_instance" {
    source = "../ec2_instance"

    # parameters for module
    instance_type       = "${var.mongod_instance_type}"
    count               = "${var.mongod_instance_count}"
    subnet_id           = "${module.VPC.aws_subnet_id}"
    key_file            = "${var.key_path}"
    security_groups     = "${module.VPC.aws_security_group_id}"
    availability_zone   = "${var.availability_zone}"
    placement_group     = "${var.mongod_instance_placement_group}"
    key_name            = "${var.key_name}"
    owner               = "${var.owner}"
    mongourl            = "${var.mongourl}"
    expire_on           = "${var.expire_on}"
    provisioner_file    = "mongod-instance-setup.sh"
    topology            = "${var.topology}"
    type                = "mongod"
}

# AWS instance with placement group for mongos
module "mongos_instance" {
    source = "../ec2_instance"

    # parameters for module
    instance_type       = "${var.mongos_instance_type}"
    count               = "${var.mongos_instance_count}"
    subnet_id           = "${module.VPC.aws_subnet_id}"
    key_file            = "${var.key_path}"
    security_groups     = "${module.VPC.aws_security_group_id}"
    availability_zone   = "${var.availability_zone}"
    placement_group     = "${var.mongos_instance_placement_group}"
    key_name            = "${var.key_name}"
    owner               = "${var.owner}"
    mongourl            = "${var.mongourl}"
    expire_on           = "${var.expire_on}"
    provisioner_file    = "generic-mongo-instance-setup.sh"
    topology            = "${var.topology}"
    type                = "mongos"
}

# AWS instance with placement group for config server
module "configserver_instance" {
    source = "../ec2_instance"

    # parameters for module
    instance_type       = "${var.configserver_instance_type}"
    count               = "${var.configserver_instance_count}"
    subnet_id           = "${module.VPC.aws_subnet_id}"
    key_file            = "${var.key_path}"
    security_groups     = "${module.VPC.aws_security_group_id}"
    availability_zone   = "${var.availability_zone}"
    placement_group     = "${var.configserver_instance_placement_group}"
    key_name            = "${var.key_name}"
    owner               = "${var.owner}"
    mongourl            = "${var.mongourl}"
    expire_on           = "${var.expire_on}"
    provisioner_file    = "generic-mongo-instance-setup.sh"
    topology            = "${var.topology}"
    type                = "configsvr"
}

# AWS instance for workload generator
module "workload_instance" {
    source = "../ec2_instance"

    # parameters for module
    instance_type       = "${var.workload_instance_type}"
    count               = "${var.workload_instance_count}"
    subnet_id           = "${module.VPC.aws_subnet_id}"
    key_file            = "${var.key_path}"
    security_groups     = "${module.VPC.aws_security_group_id}"
    availability_zone   = "${var.availability_zone}"
    placement_group     = "${var.workload_instance_placement_group}"
    key_name            = "${var.key_name}"
    owner               = "${var.owner}"
    mongourl            = "${var.mongourl}"
    expire_on           = "${var.expire_on}"
    provisioner_file    = "workload-client-setup.sh"
    topology            = "${var.topology}"
    type                = "workloadclient"
}

variable mongourl                       {}
variable owner                          {}
variable topology                       {}

# define instance types
variable mongod_instance_type           {}
variable workload_instance_type         {}
variable configserver_instance_type     { default = "m3.2xlarge" }

# define instance count
variable mongod_instance_count          { default = 0 }
variable workload_instance_count        { default = 0 }
variable configserver_instance_count    { default = 0 }

# AWS details
variable region                         {}
variable availability_zone              {}
variable key_path                       {}
variable key_name                       {}

variable expired_on                     { default = "2016-12-31" }

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
    placement_group     = "${concat("dsi-perf-",var.availability_zone)}"
    key_name            = "${var.key_name}"
    owner               = "${var.owner}"
    mongourl            = "${var.mongourl}"
    expire-on           = "${var.expired_on}"
    provisioner_file    = "mongod-instance-setup.sh"
    type                = ""
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
    placement_group     = "${concat("dsi-perf-",var.availability_zone)}"
    key_name            = "${var.key_name}"
    owner               = "${var.owner}"
    mongourl            = "${var.mongourl}"
    expire-on           = "${var.expired_on}"
    provisioner_file    = "workload-client-setup.sh"
    type                = "master"
}

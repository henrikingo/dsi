variable owner                          { default = "serverteam-perf@10gen.com" }
variable topology                       {}
variable key_file                       {}
variable key_name                       {}

# define instance types
variable mongod_instance_type                   {}
variable mongod_ebs_instance_type               { default = "c3.8xlarge" }
variable mongod_seeded_ebs_instance_type        { default = "c3.8xlarge" }
variable mongos_instance_type                   { default = "c3.4xlarge" }
variable workload_instance_type                 {}
variable configsvr_instance_type                { default = "m3.2xlarge" }

# define instance count
variable mongod_instance_count                  { default = 0 }
variable mongod_ebs_instance_count              { default = 0 }
variable mongod_seeded_ebs_instance_count       { default = 0 }
variable mongos_instance_count                  { default = 0 }
variable workload_instance_count                { default = 0 }
variable configsvr_instance_count               { default = 0 }

# define whether to use placement_group
variable mongod_instance_placement_group            { default="yes" }
variable mongod_ebs_instance_placement_group        { default="yes" }
variable mongod_seeded_ebs_instance_placement_group { default="yes" }
variable mongos_instance_placement_group            { default="yes" }
variable workload_instance_placement_group          { default="yes" }
variable configsvr_instance_placement_group         { default="no" }

# AWS details
variable region                         {}
variable availability_zone              {}
variable key_file                       {}
variable key_name                       {}

variable expire_on                      { default = "2016-12-31" }

# variables EBS support
variable mongod_ebs_size                       { default = 100 }
variable mongod_ebs_iops                       { default = 1500 }

# variable for seeded_ebs
variable mongod_seeded_ebs_snapshot_id         { default = "" }
variable mongod_seeded_ebs_iops                { default = 1500 }

variable run_fio                               { default = "true" }

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
    key_file            = "${var.key_file}"
    security_groups     = "${module.VPC.aws_security_group_id}"
    availability_zone   = "${var.availability_zone}"
    placement_group     = "${var.mongod_instance_placement_group}"
    key_name            = "${var.key_name}"
    owner               = "${var.owner}"
    expire_on           = "${var.expire_on}"
    provisioner_file    = "system-setup.sh"
    topology            = "${var.topology}"
    type                = "mongod"
    run_fio             = "${var.run_fio}"
}

# AWS instance with placement group, and EBS volume for mongod
module "mongod_ebs_instance" {
    source = "../ec2_ebs_instance"

    # parameters for module
    instance_type       = "${var.mongod_ebs_instance_type}"
    count               = "${var.mongod_ebs_instance_count}"
    subnet_id           = "${module.VPC.aws_subnet_id}"
    key_file            = "${var.key_file}"
    security_groups     = "${module.VPC.aws_security_group_id}"
    availability_zone   = "${var.availability_zone}"
    placement_group     = "${var.mongod_ebs_instance_placement_group}"
    key_name            = "${var.key_name}"
    owner               = "${var.owner}"
    expire_on           = "${var.expire_on}"
    provisioner_file    = "system-setup.sh"
    topology            = "${var.topology}"
    type                = "mongod_ebs"
    ebs_size            = "${var.mongod_ebs_size}"
    ebs_iops            = "${var.mongod_ebs_iops}"
    run_fio             = "${var.run_fio}"
}

# AWS instance with placement group, and seeded EBS volume for mongod
module "mongod_seeded_ebs_instance" {
    source = "../ec2_seeded_ebs_instance"

    # parameters for module
    instance_type           = "${var.mongod_seeded_ebs_instance_type}"
    count                   = "${var.mongod_seeded_ebs_instance_count}"
    subnet_id               = "${module.VPC.aws_subnet_id}"
    key_file                = "${var.key_file}"
    security_groups         = "${module.VPC.aws_security_group_id}"
    availability_zone       = "${var.availability_zone}"
    placement_group         = "${var.mongod_seeded_ebs_instance_placement_group}"
    key_name                = "${var.key_name}"
    owner                   = "${var.owner}"
    expire_on               = "${var.expire_on}"
    provisioner_file        = "system-setup.sh"
    topology                = "${var.topology}"
    type                    = "mongod_seeded_ebs"
    seeded_ebs_snapshot_id  = "${var.mongod_seeded_ebs_snapshot_id}"
    seeded_ebs_iops         = "${var.mongod_seeded_ebs_iops}"
    run_fio                 = "${var.run_fio}"
}

# AWS instance with placement group for mongos
module "mongos_instance" {
    source = "../ec2_instance"

    # parameters for module
    instance_type       = "${var.mongos_instance_type}"
    count               = "${var.mongos_instance_count}"
    subnet_id           = "${module.VPC.aws_subnet_id}"
    key_file            = "${var.key_file}"
    security_groups     = "${module.VPC.aws_security_group_id}"
    availability_zone   = "${var.availability_zone}"
    placement_group     = "${var.mongos_instance_placement_group}"
    key_name            = "${var.key_name}"
    owner               = "${var.owner}"
    expire_on           = "${var.expire_on}"
    provisioner_file    = "system-setup.sh"
    topology            = "${var.topology}"
    type                = "mongos"
    run_fio             = "false"
}

# AWS instance with placement group for config server
module "configsvr_instance" {
    source = "../ec2_instance"

    # parameters for module
    instance_type       = "${var.configsvr_instance_type}"
    count               = "${var.configsvr_instance_count}"
    subnet_id           = "${module.VPC.aws_subnet_id}"
    key_file            = "${var.key_file}"
    security_groups     = "${module.VPC.aws_security_group_id}"
    availability_zone   = "${var.availability_zone}"
    placement_group     = "${var.configsvr_instance_placement_group}"
    key_name            = "${var.key_name}"
    owner               = "${var.owner}"
    expire_on           = "${var.expire_on}"
    provisioner_file    = "system-setup.sh"
    topology            = "${var.topology}"
    type                = "configsvr"
    run_fio             = "false"
}

# AWS instance for workload generator
module "workload_instance" {
    source = "../ec2_instance"

    # parameters for module
    instance_type       = "${var.workload_instance_type}"
    count               = "${var.workload_instance_count}"
    subnet_id           = "${module.VPC.aws_subnet_id}"
    key_file            = "${var.key_file}"
    security_groups     = "${module.VPC.aws_security_group_id}"
    availability_zone   = "${var.availability_zone}"
    placement_group     = "${var.workload_instance_placement_group}"
    key_name            = "${var.key_name}"
    owner               = "${var.owner}"
    expire_on           = "${var.expire_on}"
    provisioner_file    = "system-setup.sh"
    topology            = "${var.topology}"
    type                = "workloadclient"
    run_fio             = "false"
}

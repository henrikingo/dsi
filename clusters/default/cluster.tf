variable mongod_instance_count      { default = 3 }
variable mongod_ebs_instance_count  { default = 0 }
variable mongod_seeded_ebs_instance_count  { default = 0 }
variable workload_instance_count    { default = 1 }

variable owner      {}

variable workload_instance_type                 {}
variable mongod_instance_type                   {}
variable mongod_ebs_instance_type               { default = "c3.8xlarge" }
variable mongod_seeded_ebs_instance_type        { default = "c3.8xlarge" }

variable workload_instance_placement_group      { default = "yes" }
variable mongod_instance_placement_group        { default = "yes" }
variable mongod_ebs_instance_placement_group    { default = "yes" }
variable mongod_seeded_ebs_instance_placement_group    { default = "yes" }

variable topology                   {}
variable availability_zone          {}
variable region                     {}
variable expire_on                  { default = "2016-12-31" }

variable mongod_seeded_ebs_snapshot_id     { default = "snap-98bea565" }
variable mongod_seeded_ebs_iops            { default = 240 }

variable mongod_ebs_size            { default = 100 }
variable mongod_ebs_iops            { default = 240 }

module "cluster" {
    source = "../modules/cluster"

    # cluster details
    mongod_instance_type    = "${var.mongod_instance_type}"
    mongod_instance_count   = "${var.mongod_instance_count}"
    workload_instance_count = "${var.workload_instance_count}"
    workload_instance_type  = "${var.workload_instance_type}"

    # Seeded EBS instance support
    mongod_ebs_instance_type    = "${var.mongod_ebs_instance_type}"
    mongod_ebs_instance_count   = "${var.mongod_ebs_instance_count}"
    mongod_ebs_iops             = "${var.mongod_ebs_iops}"
    mongod_ebs_size             = "${var.mongod_ebs_size}"


    # Seeded EBS instance support
    mongod_seeded_ebs_instance_type    = "${var.mongod_seeded_ebs_instance_type}"
    mongod_seeded_ebs_instance_count   = "${var.mongod_seeded_ebs_instance_count}"
    mongod_seeded_ebs_iops             = "${var.mongod_seeded_ebs_iops}"
    mongod_seeded_ebs_snapshot_id      = "${var.mongod_seeded_ebs_snapshot_id}"

    mongod_instance_placement_group     = "${var.mongod_instance_placement_group}"
    workload_instance_placement_group   = "${var.workload_instance_placement_group}"
    mongod_ebs_instance_placement_group = "${var.mongod_ebs_instance_placement_group}"
    mongod_seeded_ebs_instance_placement_group = "${var.mongod_seeded_ebs_instance_placement_group}"

    topology            = "${var.topology}"

    # AWS details
    availability_zone   = "${var.availability_zone}"
    region              = "${var.region}"
    expire_on           = "${var.expire_on}"

    owner               = "${var.owner}"

    key_file            = "${var.key_file}"
    key_name            = "${var.key_name}"
}

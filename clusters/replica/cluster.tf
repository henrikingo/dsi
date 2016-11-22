variable mongod_instance_count      { default = 3 }
variable workload_instance_count    { default = 1 }

variable owner      {}

variable workload_instance_type                 {}
variable mongod_instance_type                   {}
variable workload_instance_placement_group      { default = "yes" }
variable mongod_instance_placement_group        { default = "yes" }

variable topology                   {}
variable availability_zone          {}
variable region                     {}
variable expire_on                  { default = "2016-12-31" }

variable run_fio           { default = "true" }
variable runner                     { default = "missing" }
variable status                     { default = "idle" }
variable task_id                    { default = "none" }

module "cluster" {
    source = "../modules/cluster"

    # cluster details
    mongod_instance_type    = "${var.mongod_instance_type}"
    mongod_instance_count   = "${var.mongod_instance_count}"
    workload_instance_count = "${var.workload_instance_count}"
    workload_instance_type  = "${var.workload_instance_type}"

    mongod_instance_placement_group     = "${var.mongod_instance_placement_group}"
    workload_instance_placement_group   = "${var.workload_instance_placement_group}"

    topology            = "${var.topology}"

    # AWS details
    availability_zone   = "${var.availability_zone}"
    region              = "${var.region}"
    expire_on           = "${var.expire_on}"

    owner               = "${var.owner}"

    key_file            = "${var.key_file}"
    key_name            = "${var.key_name}"

    run_fio    = "${var.run_fio}"
    runner              = "${var.runner}"
    status              = "${var.status}"
    task_id             = "${var.task_id}"
}

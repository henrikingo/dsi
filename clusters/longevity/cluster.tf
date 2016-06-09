variable mongod_instance_count          { default = 9 }
variable workload_instance_count        { default = 1 }
variable mongos_instance_count          { default = 1 }
variable configserver_instance_count    { default = 3 }

variable mongourl   {}
variable owner      {}

variable workload_instance_type                 {}
variable mongod_instance_type                   {}
variable mongos_instance_type                   {}
variable configserver_instance_type             {}

variable workload_instance_placement_group      { default = "yes" }
variable mongod_instance_placement_group        { default = "yes" }
variable mongos_instance_placement_group        { default = "yes" }
variable configserver_instance_placement_group  { default = "no"}

variable topology                   {}
variable availability_zone          {}
variable region                     {}
variable expire_on                  { default = "2016-12-31" }

module "cluster" {
    source = "../modules/cluster"

    # variables
    mongourl = "${var.mongourl}"

    # cluster details
    mongod_instance_type    = "${var.mongod_instance_type}"
    mongod_instance_count   = "${var.mongod_instance_count}"
    workload_instance_count = "${var.workload_instance_count}"
    workload_instance_type  = "${var.workload_instance_type}"

    # shard special instances
    mongos_instance_type        = "${var.mongos_instance_type}"
    mongos_instance_count       = "${var.mongos_instance_count}"
    configserver_instance_type  = "${var.configserver_instance_type}"
    configserver_instance_count = "${var.configserver_instance_count}"

    mongod_instance_placement_group         = "${var.mongod_instance_placement_group}"
    mongos_instance_placement_group         = "${var.mongos_instance_placement_group}"
    configserver_instance_placement_group   = "${var.configserver_instance_placement_group}"
    workload_instance_placement_group       = "${var.workload_instance_placement_group}"

    topology            = "${var.topology}"

    # AWS details
    availability_zone   = "${var.availability_zone}"
    region              = "${var.region}"
    expire_on           = "${var.expire_on}"

    owner               = "${var.owner}"

    key_path            = "${var.key_path}"
    key_name            = "${var.key_name}"
}

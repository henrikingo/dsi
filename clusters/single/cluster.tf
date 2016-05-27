variable mongod_instance_count      { default = 1 }
variable workload_instance_count    { default = 1 }

variable mongourl   {}
variable owner      {}

variable workload_instance_type     {}
variable mongod_instance_type       {}

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

    topology            = "${var.topology}"

    # AWS details
    availability_zone   = "${var.availability_zone}"
    region              = "${var.region}"
    expire_on           = "${var.expire_on}"

    owner               = "${var.owner}"

    key_path            = "${var.key_path}"
    key_name            = "${var.key_name}"
}

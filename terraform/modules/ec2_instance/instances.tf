# define list of variables
variable "key_file"             {}
variable "key_name"             {}
variable "instance_type"        {}
variable "count"                {}
variable "subnet_id"            {}
variable "owner"                {}
variable "security_groups"      {}
variable "availability_zone"    {}
variable "placement_group"      {}
variable "expire_on"            {}
variable "provisioner_file"     {}
variable "topology"             {}
variable "type"                 {}
variable "runner"               {}
variable "runner_instance_id"   {}
variable "status"               {}
variable "task_id"              {}

# AWS instance with placement group for mongod
resource "aws_instance" "member" {
    ami                 = "${lookup(var.amis, var.availability_zone)}"
    instance_type       = "${var.instance_type}"
    count               = "${var.count}"
    subnet_id           = "${var.subnet_id}"
    private_ip          = "${lookup(var.private_ips, format("%s%s", var.type, "${count.index}"))}"

    connection {
        # The default username for our AMI
        user            = "ec2-user"

        # The path to your keyfile
        private_key        = "${file(var.key_file)}"
    }

    vpc_security_group_ids     = ["${var.security_groups}"]

    availability_zone   = "${var.availability_zone}"
    placement_group     = "${var.placement_group}"
    tenancy             = "dedicated"

    key_name = "${var.key_name}"
    tags = {
        Name               = "dsi-${var.topology}-${var.type}-${count.index}"
        owner              = "${var.owner}"
        expire-on          = "${var.expire_on}"
        test_setup         = "dsi"
        test_topology      = "${var.topology}"
        runner             = "${var.runner}"
        runner_instance_id = "${var.runner_instance_id}"
        status             = "${var.status}"
        task_id            = "${var.task_id}"
}

    ephemeral_block_device {
        device_name     = "/dev/sdc"
        virtual_name    = "ephemeral0"
    }
    ephemeral_block_device {
        device_name     = "/dev/sdd"
        virtual_name    = "ephemeral1"
    }

    associate_public_ip_address = 1

    # We run a remote provisioner on the instance after creating it.
    provisioner "file" {
        connection {
            timeout = "10m"
        }
        source      = "${format("./remote-scripts/%s", var.provisioner_file)}"
        destination = "/tmp/provision.sh"
    }

    provisioner "remote-exec" {
        connection {
            timeout = "10m"
        }
        inline = [
            "chmod +x /tmp/provision.sh",
            "/tmp/provision.sh ${var.type} false"
        ]
    }
}


resource "aws_vpc" "main" {
    cidr_block = "10.2.0.0/16"
    enable_dns_hostnames = true

    tags {
        Name = "${var.user}-single-vpc"
        TestSetup = "dsi"
        TestTopology = "single"
    }
}

resource "aws_internet_gateway" "gw" {
    vpc_id = "${aws_vpc.main.id}"
}

resource "aws_subnet" "main" {
    vpc_id = "${aws_vpc.main.id}"
    cidr_block = "10.2.0.0/24"
    availability_zone = "us-west-2a"

    tags {
        Name = "${var.user}-single-subnet"
        TestSetup = "dsi"
        TestTopology = "single"
    }
}

resource "aws_route_table" "r" {
    vpc_id = "${aws_vpc.main.id}"
    route {
        cidr_block = "0.0.0.0/0"
        gateway_id = "${aws_internet_gateway.gw.id}"
    }

    tags {
        Name = "${var.user}-dsi-routing"
        TestSetup = "dsi"
        TestTopology = "single"
    }
}

resource "aws_route_table_association" "a" {
    subnet_id = "${aws_subnet.main.id}"
    route_table_id = "${aws_route_table.r.id}"
}

resource "aws_security_group" "default" {
    name = "${var.user}-single-default"
    description = "${var.user} config for single cluster"
    vpc_id = "${aws_vpc.main.id}"

    # SSH access from anywhere
    ingress {
        from_port = 22
        to_port = 22
        protocol = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    # mongodb access from VPC
    ingress {
        from_port = 27017
        to_port = 27019
        protocol = "tcp"
        cidr_blocks = ["10.2.0.0/16"]
    }

    # allow all egress
    egress {
        from_port = 0
        to_port = 0
        protocol = "-1"
        cidr_blocks = ["0.0.0.0/0"]
    }
}


resource "aws_instance" "member" {
    # Amazon Linux AMI 2015.09.1 (HVM), SSD Volume Type - ami-60b6c60a
    # ami = "ami-60b6c60a"
    # Amazon Linux AMI 2015.03 (HVM), SSD Volume Type (us-west-2a)
    ami = "ami-e7527ed7"

    instance_type = "${var.secondary_type}"

    count = "${var.count}"

    subnet_id = "${aws_subnet.main.id}"
    private_ip = "${lookup(var.instance_ips, count.index)}"

    connection {
        # The default username for our AMI
        user = "ec2-user"

        # The path to your keyfile
        key_file = "${var.key_path}"
    }

    security_groups = ["${aws_security_group.default.id}"]
    availability_zone = "us-west-2a"
    placement_group = "dsi-single-perf-us-west-2a"
    tenancy = "dedicated"

    key_name = "${var.key_name}"
    tags = {
        Name = "${var.user}-single-member-${count.index}"
        TestSetup = "dsi"
        TestTopology = "single"
        owner = "${var.owner}"
        expire-on = "2016-07-15"
    }

    ephemeral_block_device {
        device_name = "/dev/sdc"
        virtual_name = "ephemeral0"
        # delete_on_termination = true
    }
    ephemeral_block_device {
        device_name = "/dev/sdd"
        virtual_name = "ephemeral1"
        # delete_on_termination = true
    }

    associate_public_ip_address = 1

    # We run a remote provisioner on the instance after creating it.
    provisioner "file" {
        source = "../remote-scripts/mongod-instance-setup.sh"
        destination = "/tmp/provision.sh"
    }

    provisioner "remote-exec" {
        connection {
            timeoout = "10m"
        }
        inline = [
            "chmod +x /tmp/provision.sh",
            "/tmp/provision.sh ${var.mongourl}"
        ]
    }
}

resource "aws_instance" "master" {
    # Amazon Linux AMI 2015.09.1 (HVM), SSD Volume Type - ami-60b6c60a
    # ami = "ami-60b6c60a"
    # Amazon Linux AMI 2015.03 (HVM), SSD Volume Type (us-west-2a)
    ami = "ami-e7527ed7"

    instance_type = "${var.primary_type}"

    subnet_id = "${aws_subnet.main.id}"
    private_ip = "${lookup(var.instance_ips, concat("master", count.index))}"
    count = "${var.mastercount}"

    connection {
        # The default username for our AMI
        user = "ec2-user"

        # The path to your keyfile
        key_file = "${var.key_path}"
    }

    security_groups = ["${aws_security_group.default.id}"]
    availability_zone = "us-west-2a"
    placement_group = "dsi-single-perf-us-west-2a"
    tenancy = "dedicated"

    key_name = "${var.key_name}"
    tags = {
        Name = "${var.user}-single-master-${count.index}"
        TestSetup = "dsi"
        TestTopology = "single"
        owner = "${var.owner}"
        expire-on = "2016-07-15"
    }

    associate_public_ip_address = 1

    # We run a remote provisioner on the instance after creating it.
    provisioner "file" {
        source = "../remote-scripts/workload-client-setup.sh"
        destination = "/tmp/provision.sh"
    }

    provisioner "remote-exec" {
        connection {
            timeoout = "10m"
        }
        inline = [
            "chmod +x /tmp/provision.sh",
            "/tmp/provision.sh ${var.mongourl}"
        ]
    }
}

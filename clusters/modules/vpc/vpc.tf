# input variables
variable topology           {}
variable availability_zone  {}
variable owner              {}
variable runner             {} # Hostname of the machine using it
variable status             {} # Idle, Running
variable task_id            {}

# resource definition
resource "aws_vpc" "main" {
    cidr_block = "10.2.0.0/16"
    enable_dns_hostnames = true

    tags {
        Name = "dsi-${var.topology}-vpc"
        TestSetup = "dsi"
        TestTopology = "${var.topology}"
        Owner = "${var.owner}"
        runner = "${var.runner}"
        status = "${var.status}"
        task_id         = "${var.task_id}"
    }
}

resource "aws_internet_gateway" "gw" {
    vpc_id = "${aws_vpc.main.id}"
}

resource "aws_subnet" "main" {
    vpc_id = "${aws_vpc.main.id}"
    cidr_block = "10.2.0.0/24"
    availability_zone = "${var.availability_zone}"

    tags {
        Name = "dsi-${var.topology}-subnet"
        TestSetup = "dsi"
        TestTopology = "${var.topology}"
        Owner = "${var.owner}"
        runner          = "${var.runner}"
        status          = "${var.status}"
        task_id         = "${var.task_id}"
    }
}

resource "aws_route_table" "r" {
    vpc_id = "${aws_vpc.main.id}"
    route {
        cidr_block = "0.0.0.0/0"
        gateway_id = "${aws_internet_gateway.gw.id}"
    }

    tags {
        Name = "dsi-dsi-routing"
        TestSetup = "dsi"
        TestTopology = "${topology}"
        Owner = "${var.owner}"
        runner          = "${var.runner}"
        status          = "${var.status}"
        task_id         = "${var.task_id}"
    }
}

resource "aws_route_table_association" "a" {
    subnet_id = "${aws_subnet.main.id}"
    route_table_id = "${aws_route_table.r.id}"
}

resource "aws_security_group" "default" {
    name = "dsi-${var.topology}-default"
    description = "DSI config for ${var.topology} cluster"
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
        from_port = 27016
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

# output variables
output "aws_subnet_id" { value = "${aws_subnet.main.id}" }
output "aws_security_group_id" { value = "${aws_security_group.default.id}" }

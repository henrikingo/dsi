
resource "aws_vpc" "main" {
    cidr_block = "10.2.0.0/16"
    enable_dns_hostnames = true

    tags {
        Name = "${var.user}-shard-vpc"
        TestSetup = "dsi"
        TestTopology = "shard"
    }
}

resource "aws_internet_gateway" "gw" {
    vpc_id = "${aws_vpc.main.id}"
}

resource "aws_subnet" "main" {
    vpc_id = "${aws_vpc.main.id}"
    cidr_block = "10.2.1.0/24"
    availability_zone = "us-west-2a"

    tags {
        Name = "${var.user}-shard-subnet"
        TestSetup = "dsi"
        TestTopology = "shard"
    }
}

resource "aws_route_table" "r" {
    vpc_id = "${aws_vpc.main.id}"
    route {
        cidr_block = "0.0.0.0/0"
        gateway_id = "${aws_internet_gateway.gw.id}"
    }

    tags {
        Name = "${var.user}-shard-routing"
        TestSetup = "dsi"
        TestTopology = "shard"
    }
}

resource "aws_route_table_association" "a" {
    subnet_id = "${aws_subnet.main.id}"
    route_table_id = "${aws_route_table.r.id}"
}

resource "aws_security_group" "shard-default" {
    name = "${var.user}-shard-default"
    description = "${var.user} config for shard"
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


resource "aws_instance" "shardmember" {
    # Amazon Linux AMI 2015.03 (HVM), SSD Volume Type
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

    security_groups = ["${aws_security_group.shard-default.id}"]
    availability_zone = "us-west-2a"
    placement_group = "dsi-shard-perf-us-west-2a"
    tenancy = "dedicated"

    key_name = "${var.key_name}"
    tags = {
        Name = "${var.user}-shard-member-${count.index}"
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
    provisioner "remote-exec" {
        connection {
            timeoout = "10m"
        }
        inline = [
            "sudo yum -y -q install git fio wget sysstat dstat perf xfsprogs",
            "mkdir mongodb; curl --retry 10 %%MONGO_URL%% | tar zxv -C mongodb; cd mongodb; mv */bin .; cd ~ ",
            "mkdir -p ~/bin",
            "ln -s ~/mongodb/bin/mongo ~/bin/mongo",
            "dev=/dev/xvdc; sudo umount $dev; sudo mkfs.xfs -f $dev; sudo mount $dev",
            "sudo chmod 777 /media/ephemeral0",
            "sudo chown ec2-user /media/ephemeral0",
            # "sudo umount /dev/xvdd; sudo mkswap /dev/xvdd; sudo swapon /dev/xvdd",
            "dev=/dev/xvdd; dpath=/media/ephemeral1; sudo mkdir -p $dpath; sudo umount $dev; sudo mkfs.xfs -f $dev; sudo mount $dev $dpath; ",
            "sudo chmod 777 /media/ephemeral1",
            "sudo chown ec2-user /media/ephemeral1",
            "ln -s /media/ephemeral0 ~/data",
            "ln -s /media/ephemeral1 ~/journal",
            "echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled",
            "echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/defrag",
            "echo f | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus",
            "echo f0 | sudo tee /sys/class/net/eth0/queues/tx-0/xps_cpus",
            "echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCmHUZLsuGvNUlCiaZ83jS9f49S0plAtCH19Z2iATOYPH1XE2T8ULcHdFX2GkYiaEqI+fCf1J1opif45sW/5yeDtIp4BfRAdOu2tOvkKvzlnGZndnLzFKuFfBPcysKyrGxkqBvdupOdUROiSIMwPcFgEzyLHk3pQ8lzURiJNtplQ82g3aDi4wneLDK+zuIVCl+QdP/jCc0kpYyrsWKSbxi0YrdpG3E25Q4Rn9uom58c66/3h6MVlk22w7/lMYXWc5fXmyMLwyv4KndH2u3lV45UAb6cuJ6vn6wowiD9N9J1GS57m8jAKaQC1ZVgcZBbDXMR8fbGdc9AH044JVtXe3lT shardtest@test.mongo' | tee -a ~/.ssh/authorized_keys",
            "fio --directory=/media/ephemeral0 --name fio_test_file --direct=1 --rw=randwrite --bs=16k --size=1G --numjobs=16 --time_based --runtime=60 --group_reporting --norandommap",
            "fio --directory=/media/ephemeral1 --name fio_test_file --direct=1 --rw=randwrite --bs=16k --size=1G --numjobs=16 --time_based --runtime=60 --group_reporting --norandommap",
            "rm *.tgz",
            "rm *.rpm",
            "ls"
        ]
    }
}

resource "aws_instance" "master" {
    # Amazon Linux AMI 2015.03 (HVM), SSD Volume Type
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

    security_groups = ["${aws_security_group.shard-default.id}"]
    availability_zone = "us-west-2a"
    placement_group = "dsi-shard-perf-us-west-2a"
    tenancy = "dedicated"

    key_name = "${var.key_name}"
    tags = {
        Name = "${var.user}-shard-master-${count.index}"
        TestSetup = "dsi"
        TestTopology = "shard"
        owner = "${var.owner}"
        expire-on = "2016-07-15"
    }

    associate_public_ip_address = 1

    # We run a remote provisioner on the instance after creating it.
    provisioner "file" {
        source = "../remote-scripts/workload-client-provision.bash"
        destination = "/tmp/provision.bash"
    }

    provisioner "remote-exec" {
        connection {
            timeoout = "10m"
        }
        inline = [
            "chmod +x /tmp/provision.bash",
            "/tmp/provision.bash ${var.mongourl}"
        ]
    }
}

resource "aws_instance" "configserver" {
    # Amazon Linux AMI 2015.03 (HVM), SSD Volume Type
    ami = "ami-e7527ed7"

    instance_type = "${var.configserver_type}"

    # config server fixed at 3
    count = "${var.configcount}"

    subnet_id = "${aws_subnet.main.id}"
    private_ip = "${lookup(var.instance_ips, concat("config", count.index))}"

    connection {
        # The default username for our AMI
        user = "ec2-user"

        # The path to your keyfile
        key_file = "${var.key_path}"
    }

    security_groups = ["${aws_security_group.shard-default.id}"]
    availability_zone = "us-west-2a"

    key_name = "${var.key_name}"
    tags = {
        Name = "${var.user}-shard-config-${count.index}"
        TestSetup = "dsi"
        TestTopology = "shard"
        owner = "${var.owner}"
        expire-on = "2016-07-15"
    }

    associate_public_ip_address = 1

    # We run a remote provisioner on the instance after creating it.
    provisioner "remote-exec" {
        connection {
            timeoout = "10m"
        }
        inline = [
            "sudo yum -y -q install tmux git wget sysstat dstat perf",
            "mkdir mongodb; curl --retry 10 ${var.mongourl} | tar zxv -C mongodb; cd mongodb; mv */bin .; cd ~ ",
            "mkdir -p ~/bin",
            "ln -s ~/mongodb/bin/mongo ~/bin/mongo",
            "echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled",
            "echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/defrag",
            "echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCmHUZLsuGvNUlCiaZ83jS9f49S0plAtCH19Z2iATOYPH1XE2T8ULcHdFX2GkYiaEqI+fCf1J1opif45sW/5yeDtIp4BfRAdOu2tOvkKvzlnGZndnLzFKuFfBPcysKyrGxkqBvdupOdUROiSIMwPcFgEzyLHk3pQ8lzURiJNtplQ82g3aDi4wneLDK+zuIVCl+QdP/jCc0kpYyrsWKSbxi0YrdpG3E25Q4Rn9uom58c66/3h6MVlk22w7/lMYXWc5fXmyMLwyv4KndH2u3lV45UAb6cuJ6vn6wowiD9N9J1GS57m8jAKaQC1ZVgcZBbDXMR8fbGdc9AH044JVtXe3lT shardtest@test.mongo' | tee -a ~/.ssh/authorized_keys",
            "echo f | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus",
            "echo f0 | sudo tee /sys/class/net/eth0/queues/tx-0/xps_cpus",
            "rm *.tgz",
            "rm *.rpm",
            "ls"
        ]
    }
}

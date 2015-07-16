
resource "aws_vpc" "main" {
    cidr_block = "10.2.0.0/16"
    enable_dns_hostnames = true

    tags {
        Name = "${var.user}-longevity-vpc"
    }
}

resource "aws_internet_gateway" "gw" {
    vpc_id = "${aws_vpc.main.id}"
}

resource "aws_subnet" "main" {
    vpc_id = "${aws_vpc.main.id}"
    cidr_block = "10.2.5.0/24"
    availability_zone = "us-west-2b"

    tags {
        Name = "${var.user}-longevity-subnet"
    }
}

resource "aws_route_table" "r" {
    vpc_id = "${aws_vpc.main.id}"
    route {
        cidr_block = "0.0.0.0/0"
        gateway_id = "${aws_internet_gateway.gw.id}"
    }

    tags {
        Name = "${var.user}-longevity-routing"
    }
}

resource "aws_route_table_association" "a" {
    subnet_id = "${aws_subnet.main.id}"
    route_table_id = "${aws_route_table.r.id}"
}

resource "aws_security_group" "longevity-default" {
    name = "${var.user}-longevity-default"
    description = "${var.user} config for longevity"
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

    security_groups = ["${aws_security_group.longevity-default.id}"]
    availability_zone = "us-west-2b"
    # placement_group = "${var.user}-longevity-perf"
    # tenancy = "dedicated"

    key_name = "${var.key_name}"
    tags = {
        Name = "${var.user}-longevity-member-${count.index}"
        owner = "${var.owner}"
        expire-on = "2015-07-15"
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
            "sudo yum -y install git wget sysstat dstat perf xfsprogs",
            "mkdir mongodb; curl %%MONGO_URL%% | tar zxv -C mongodb; cd mongodb; mv */bin . ",
            "mkdir -p ~/bin",
            "ln -s ~/mongodb/bin/mongo ~/bin/mongo",
            "dev=/dev/xvdc; sudo umount $dev; sudo mkfs.xfs -f $dev; sudo mount $dev",
            "sudo chmod 777 /media/ephemeral0",
            "sudo chown ec2-user /media/ephemeral0",
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

    security_groups = ["${aws_security_group.longevity-default.id}"]
    availability_zone = "us-west-2b"

    key_name = "${var.key_name}"
    tags = {
        Name = "${var.user}-longevity-master-${count.index}"
        owner = "${var.owner}"
        expire-on = "2015-07-15"
    }

    associate_public_ip_address = 1

    # We run a remote provisioner on the instance after creating it.
    provisioner "remote-exec" {
        connection {
            timeoout = "10m"
        }
        inline = [
            "sudo yum -y install tmux git wget sysstat dstat perf",
            "mkdir mongodb; curl %%MONGO_URL%% | tar zxv -C mongodb; cd mongodb; mv */bin . ",
            "mkdir -p ~/bin",
            "ln -s ~/mongodb/bin/mongo ~/bin/mongo",
            "wget --no-check-certificate --no-cookies --header 'Cookie: oraclelicense=accept-securebackup-cookie' http://download.oracle.com/otn-pub/java/jdk/7u71-b14/jdk-7u71-linux-x64.rpm; sudo rpm -i jdk-7u71-linux-x64.rpm;",
            "sudo /usr/sbin/alternatives --install /usr/bin/java java /usr/java/jdk1.7.0_71/bin/java 20000",
            "wget --no-check-certificate http://central.maven.org/maven2/org/mongodb/mongo-java-driver/2.13.0/mongo-java-driver-2.13.0.jar",
            "echo 'export CLASSPATH=~/mongo-java-driver-2.13.0.jar:$CLASSPATH' >> ~/.bashrc",
            "cd ~; git clone https://github.com/rzh/sysbench-mongodb.git",
            "cd ~; git clone -b shard-test https://github.com/rzh/YCSB.git",
            "curl https://raw.githubusercontent.com/rzh/utils/master/mongodb/scripts/install_maven.sh | sudo bash",
            "source /etc/profile.d/maven.sh; cd /home/ec2-user/YCSB/ycsb-mongodb; ./setup.sh",
            "echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled", 
            "echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/defrag", 
            "echo f | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus",
            "echo f0 | sudo tee /sys/class/net/eth0/queues/tx-0/xps_cpus",
            "echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCmHUZLsuGvNUlCiaZ83jS9f49S0plAtCH19Z2iATOYPH1XE2T8ULcHdFX2GkYiaEqI+fCf1J1opif45sW/5yeDtIp4BfRAdOu2tOvkKvzlnGZndnLzFKuFfBPcysKyrGxkqBvdupOdUROiSIMwPcFgEzyLHk3pQ8lzURiJNtplQ82g3aDi4wneLDK+zuIVCl+QdP/jCc0kpYyrsWKSbxi0YrdpG3E25Q4Rn9uom58c66/3h6MVlk22w7/lMYXWc5fXmyMLwyv4KndH2u3lV45UAb6cuJ6vn6wowiD9N9J1GS57m8jAKaQC1ZVgcZBbDXMR8fbGdc9AH044JVtXe3lT shardtest@test.mongo' | tee -a ~/.ssh/authorized_keys",
            "chmod 400 ~/.ssh/id_rsa",
            "rm *.tgz",
            "rm *.rpm",
            "ls"
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

    security_groups = ["${aws_security_group.longevity-default.id}"]
    availability_zone = "us-west-2b"

    key_name = "${var.key_name}"
    tags = {
        Name = "${var.user}-longevity-config-${count.index}"
        owner = "${var.owner}"
        expire-on = "2015-07-15"
    }

    associate_public_ip_address = 1

    # We run a remote provisioner on the instance after creating it.
    provisioner "remote-exec" {
        connection {
            timeoout = "10m"
        }
        inline = [
            "sudo yum -y install tmux git wget sysstat dstat perf",
            "mkdir mongodb; curl %%MONGO_URL%% | tar zxv -C mongodb; cd mongodb; mv */bin . ",
            "mkdir -p ~/bin",
            "ln -s ~/mongodb/bin/mongo ~/bin/mongo",
            "echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled", 
            "echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/defrag",
            "echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCmHUZLsuGvNUlCiaZ83jS9f49S0plAtCH19Z2iATOYPH1XE2T8ULcHdFX2GkYiaEqI+fCf1J1opif45sW/5yeDtIp4BfRAdOu2tOvkKvzlnGZndnLzFKuFfBPcysKyrGxkqBvdupOdUROiSIMwPcFgEzyLHk3pQ8lzURiJNtplQ82g3aDi4wneLDK+zuIVCl+QdP/jCc0kpYyrsWKSbxi0YrdpG3E25Q4Rn9uom58c66/3h6MVlk22w7/lMYXWc5fXmyMLwyv4KndH2u3lV45UAb6cuJ6vn6wowiD9N9J1GS57m8jAKaQC1ZVgcZBbDXMR8fbGdc9AH044JVtXe3lT shardtest@test.mongo' | tee -a ~/.ssh/authorized_keys",
            "echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled", 
            "echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/defrag", 
            "echo f | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus",
            "echo f0 | sudo tee /sys/class/net/eth0/queues/tx-0/xps_cpus",
            "rm *.tgz",
            "rm *.rpm",
            "ls"
        ]
    }
}


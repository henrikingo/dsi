#!/bin/bash
#
# System setup script (run on each instance after launch by terraform)
#
# ./system-setup.sh [WITH_EBS] [WITH_HT]
#
# WITH_EBS:       "with_ebs" or "with_seeded_ebs" to add EBS partition
# WITH_HT:        "yes" to leave hyper-threaded cores online. Default is to disable ht.
#
WITH_EBS="${1:-false}"
WITH_HT="${2:-false}"

sudo yum -y -q install tmux git wget sysstat dstat perf fio xfsprogs krb5-libs openldap-devel cyrus-sasl cyrus-sasl-devel cyrus-sasl-gssapi cyrus-sasl-lib cyrus-sasl-md5 net-snmp net-snmp-devel net-snmp-libs net-snmp-utils python2-pip numactl


if [ "${WITH_HT}" != "yes" ]; then
    # Disable hyperthreading.
    #
    # This involves turning off cpus tied to extra threads.  Cores is the
    # total number of real cores per socket in the system. Cpus is the
    # number of cpus linux thinks it has. We want to leave on one cpu per
    # real core.  On existing systems, cpus 0 through $total_cores all map
    # to different physical cores. We are turning off all cpus beyond
    # that.

    cores=$(lscpu | egrep Core | egrep socket | cut -d : -f 2)
    sockets=$(lscpu | egrep Socket |  cut -d : -f 2)
    cpus=$(lscpu | egrep "CPU\(s\)" | head -1 | cut -d : -f 2)
    total_cores=$(($cores*$sockets))
    for i in `seq $total_cores $cpus`; do echo 0 | sudo tee /sys/devices/system/cpu/cpu$i/online; done
fi

dev=/dev/xvdc; sudo umount $dev; sudo mkfs.xfs -f $dev; sudo mount $dev
sudo chmod 777 /media/ephemeral0
sudo chown ec2-user /media/ephemeral0

# Mount $1 at $2, if $3 == "true" (default), also format (XFS)
prepare_disk() {
    disk=$1;  shift;
    mount_path=$1; shift;
    format="${1:-yes}"

    sudo mkdir -p $mount_path
    sudo umount $disk
    if [ "$format" == "yes" ]; then
        sudo mkfs.xfs -f $disk
    fi
    # Set noatime, readahead: https://docs.mongodb.com/manual/administration/production-notes/#recommended-configuration
    sudo mount $disk $mount_path -o noatime
    sudo blockdev --setra 32 $disk
    sudo chmod 777 $mount_path
    sudo chown -R ec2-user:ec2-user $mount_path
}
prepare_disk "/dev/xvdc" "/media/ephemeral0"
prepare_disk "/dev/xvdd" "/media/ephemeral1"

if [ "${WITH_EBS}" == "with_ebs" ]; then
    # Prepare empty EBS volume
    prepare_disk "/dev/xvde" "/media/ebs"
    prepare_disk "/dev/xvdf" "/media/ebs2"
    ln -s /media/ebs data
elif [ "${WITH_EBS}" == "with_seeded_ebs" ]; then
    # Will not format disk for seeded EBS partition.
    prepare_disk "/dev/xvde" "/media/ebs" "no"
    prepare_disk "/dev/xvdf" "/media/ebs2"
    ln -s /media/ebs data

    # Warm up EBS partition in order to get better read performance. This is due to this EBS
    # is created via snapshot.
    # See doc: http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-initialize.html
    sudo fio --filename=/dev/xvde --rw=randread --bs=128k --iodepth=32 --ioengine=libaio --direct=1 --name=volume-initialize --status-interval=300
else
    # Default to SSD only instance
    ln -s /media/ephemeral0 data
fi

# ~/mongodb is a symlink into data
ln -s data/mongodb mongodb

# mongodb production recommended configuration
echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
echo f | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus
echo f0 | sudo tee /sys/class/net/eth0/queues/tx-0/xps_cpus

# set ulimit nofile for ec2-user
echo "ec2-user           soft    nofile          65535" | sudo tee -a /etc/security/limits.conf
echo "ec2-user           hard    nofile          65535" | sudo tee -a /etc/security/limits.conf

echo "ec2-user   soft   core   unlimited" | sudo tee -a /etc/security/limits.conf
echo "ec2-user   hard   core   unlimited" | sudo tee -a /etc/security/limits.conf
echo "/home/ec2-user/data/logs/core.%e.%p.%h.%t" |sudo tee -a  /proc/sys/kernel/core_pattern

echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCmHUZLsuGvNUlCiaZ83jS9f49S0plAtCH19Z2iATOYPH1XE2T8ULcHdFX2GkYiaEqI+fCf1J1opif45sW/5yeDtIp4BfRAdOu2tOvkKvzlnGZndnLzFKuFfBPcysKyrGxkqBvdupOdUROiSIMwPcFgEzyLHk3pQ8lzURiJNtplQ82g3aDi4wneLDK+zuIVCl+QdP/jCc0kpYyrsWKSbxi0YrdpG3E25Q4Rn9uom58c66/3h6MVlk22w7/lMYXWc5fXmyMLwyv4KndH2u3lV45UAb6cuJ6vn6wowiD9N9J1GS57m8jAKaQC1ZVgcZBbDXMR8fbGdc9AH044JVtXe3lT shardtest@test.mongo' | tee -a ~/.ssh/authorized_keys

# Install jasper
cd ~/data
mkdir tmp
cd tmp

# <install-java>
curl -O --retry 10 -fsS \
  https://s3-us-west-2.amazonaws.com/dsi-donot-remove/java/jdk-8u162-linux-x64.rpm
sudo rpm -i jdk-8u162-linux-x64.rpm
sudo /usr/sbin/alternatives --install /usr/bin/java java /usr/java/jdk1.8.0_162/bin/java 20000
# </install-java>

# Please refer to README.md in jasper.proto's directory on steps for updating jasper.proto and the
# curator binary.
curl -o curator.tar.gz --retry 10 -LsS https://s3.amazonaws.com/boxes.10gen.com/build/curator/curator-dist-rhel70-7b53534535c6df6ea8fdbc38413a649cec3550d2.tar.gz
tar xvf curator.tar.gz

sudo cp ./curator /usr/local/bin/curator
curator --version

# Use `tee` here instead of `cat` to retain sudo privilege when writing the heredoc.
sudo tee /etc/systemd/system/jasper.service > /dev/null <<'EOF'
[Unit]
Description=Jasper Process Management Service
After=network.target

[Service]
ExecStart=/usr/local/bin/curator jasper grpc --host 0.0.0.0
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
User=ec2-user

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable jasper
sudo systemctl start jasper

exit 0

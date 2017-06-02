#!/bin/bash
#
# System setup script (run on each instance after launch by terraform)
#
# ./system-setup.sh INSTANCE_TYPE  [WITH_EBS] [FIO]
#
# INSTANCE_TYPE:  mongod, mongos, configsvr or workloadclient
# WITH_EBS:       "with_ebs" or "with_seeded_ebs" to add EBS partition
#
INSTANCE_TYPE="${1}"
WITH_EBS="${2:-false}"

sudo yum -y -q install tmux git wget sysstat dstat perf fio xfsprogs

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
    ln -s /media/ebs data

    # Warm up EBS partition in order to get better read performance. This is due to this EBS
    # is created via snapshot.
    # See doc: http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-initialize.html
    sudo fio --filename=/dev/xvde --rw=randread --bs=128k --iodepth=32 --ioengine=libaio --direct=1 --name=volume-initialize --status-interval=300
else
    # Default to SSD only instance
    ln -s /media/ephemeral0 data
fi

echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
echo f | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus
echo f0 | sudo tee /sys/class/net/eth0/queues/tx-0/xps_cpus

# set ulimit nofile for ec2-user
echo "ec2-user           soft    nofile          65535" | sudo tee -a /etc/security/limits.conf
echo "ec2-user           hard    nofile          65535" | sudo tee -a /etc/security/limits.conf

echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCmHUZLsuGvNUlCiaZ83jS9f49S0plAtCH19Z2iATOYPH1XE2T8ULcHdFX2GkYiaEqI+fCf1J1opif45sW/5yeDtIp4BfRAdOu2tOvkKvzlnGZndnLzFKuFfBPcysKyrGxkqBvdupOdUROiSIMwPcFgEzyLHk3pQ8lzURiJNtplQ82g3aDi4wneLDK+zuIVCl+QdP/jCc0kpYyrsWKSbxi0YrdpG3E25Q4Rn9uom58c66/3h6MVlk22w7/lMYXWc5fXmyMLwyv4KndH2u3lV45UAb6cuJ6vn6wowiD9N9J1GS57m8jAKaQC1ZVgcZBbDXMR8fbGdc9AH044JVtXe3lT shardtest@test.mongo' | tee -a ~/.ssh/authorized_keys

echo INSTANCE_TYPE= $INSTANCE_TYPE

# echo
# echo "Compile fio from source, because the stock fio on Amazon Linux didn't work with ioengine=net"

sudo yum groupinstall -y --quiet "Development tools"
sudo yum install -y --quiet zlib-devel
# git clone --quiet https://github.com/axboe/fio
# cd fio
# git checkout e8750877dcd5b748cc7100654f9d9dff770d0c83
# ./configure
# make
# mv fio ../netfio
# cd ..
# echo
# echo

# Workload setup
if [ "$INSTANCE_TYPE" == "workloadclient" ]; then
    # TODO: For now we setup everything each time. Ideally we'd do the Java install for ycsb only and pip for custom workloads only.
    # That would require upper layers to pass down the test_control.run[].type parameter.

    # YCSB dependencies
    curl -O --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/java/jdk-7u71-linux-x64.rpm; sudo rpm -i jdk-7u71-linux-x64.rpm;
    sudo /usr/sbin/alternatives --install /usr/bin/java java /usr/java/jdk1.7.0_71/bin/java 20000
    curl -O --retry 10 https://oss.sonatype.org/content/repositories/releases/org/mongodb/mongo-java-driver/3.2.2/mongo-java-driver-3.2.2.jar
    echo 'export CLASSPATH=~/mongo-java-driver-3.2.2.jar:$CLASSPATH' >> ~/.bashrc
    curl --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/utils/install_maven.sh | sudo bash
    # Remove the jdk rpm
    rm *.rpm || true

# custom workloads dependencies
    sudo pip install argparse python-dateutil pytz
fi



exit 0

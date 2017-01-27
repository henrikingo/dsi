#!/bin/bash
#
# System setup script (run on each instance after launch by terraform)
#
# ./system-setup.sh INSTANCE_TYPE  [WITH_EBS] [FIO]
#
# INSTANCE_TYPE:  mongod, mongos, configsvr or workloadclient
# WITH_EBS:       "with_ebs" or "with_seeded_ebs" to add EBS partition
# RUN_FIO:            If "false", skip fio tests
#
INSTANCE_TYPE="${1}"
WITH_EBS="${2:-false}"
RUN_FIO="${3:-true}"

sudo yum -y -q install tmux git wget sysstat dstat perf fio xfsprogs

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
    sudo mount $disk $mount_path
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
    ln -s /media/ebs2 journal
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
    ln -s /media/ephemeral1 journal # Superfluous on the workload client, but does no harm either
fi

echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
echo f | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus
echo f0 | sudo tee /sys/class/net/eth0/queues/tx-0/xps_cpus

# set ulimit nofile for ec2-user
echo "ec2-user           soft    nofile          65535" | sudo tee -a /etc/security/limits.conf
echo "ec2-user           hard    nofile          65535" | sudo tee -a /etc/security/limits.conf

echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCmHUZLsuGvNUlCiaZ83jS9f49S0plAtCH19Z2iATOYPH1XE2T8ULcHdFX2GkYiaEqI+fCf1J1opif45sW/5yeDtIp4BfRAdOu2tOvkKvzlnGZndnLzFKuFfBPcysKyrGxkqBvdupOdUROiSIMwPcFgEzyLHk3pQ8lzURiJNtplQ82g3aDi4wneLDK+zuIVCl+QdP/jCc0kpYyrsWKSbxi0YrdpG3E25Q4Rn9uom58c66/3h6MVlk22w7/lMYXWc5fXmyMLwyv4KndH2u3lV45UAb6cuJ6vn6wowiD9N9J1GS57m8jAKaQC1ZVgcZBbDXMR8fbGdc9AH044JVtXe3lT shardtest@test.mongo' | tee -a ~/.ssh/authorized_keys

echo RUN_FIO= $RUN_FIO
echo INSTANCE_TYPE= $INSTANCE_TYPE
if [ "${RUN_FIO}" != "false" ]; then
    fio --directory=/media/ephemeral0 --name fio_test_file --direct=1 --rw=randwrite --bs=16k --size=1G --numjobs=16 --time_based --runtime=60 --group_reporting --norandommap
    fio --directory=/media/ephemeral1 --name fio_test_file --direct=1 --rw=randwrite --bs=16k --size=1G --numjobs=16 --time_based --runtime=60 --group_reporting --norandommap
fi

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

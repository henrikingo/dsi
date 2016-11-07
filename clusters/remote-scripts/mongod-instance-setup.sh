#!/bin/bash

# To also partition EBS partition
WITH_EBS=$1

// to format a partition to xfs, and mount it
prepare_disk() {
    disk=$1;  shift;
    mount_path=$1

    sudo mkdir -p $mount_path
    sudo umount $disk
    sudo mkfs.xfs -f $disk
    sudo mount $disk $mount_path
    sudo chmod 777 $mount_path
    sudo chown -R ec2-user:ec2-user $mount_path
}

sudo yum -y -q install git fio wget sysstat dstat perf xfsprogs

prepare_disk "/dev/xvdc" "/media/ephemeral0"
prepare_disk "/dev/xvdd" "/media/ephemeral1"

if [ "${WITH_EBS}" == "with_ebs" ]; then
    # Prepare empty EBS volume
    prepare_disk "/dev/xvde" "/media/ebs"
    ln -s /media/ebs ~/data
elif [ "${WITH_EBS}" == "with_seeded_ebs" ]; then
    # Will not format disk for seeded EBS partition.
    sudo mkdir -p /media/ebs
    sudo mount /dev/xvde /media/ebs
    sudo chmod 777 /media/ebs
    sudo chown -R ec2-user:ec2-user /media/ebs
    ln -s /media/ebs ~/data
else
    # Default to SSD only instance
    ln -s /media/ephemeral0 ~/data
    ln -s /media/ephemeral1 ~/journal
fi

echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
echo f | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus
echo f0 | sudo tee /sys/class/net/eth0/queues/tx-0/xps_cpus

# set ulimit nofile for ec2-user
echo "ec2-user           soft    nofile          10000" | sudo tee -a /etc/security/limits.conf
echo "ec2-user           hard    nofile          63536" | sudo tee -a /etc/security/limits.conf

echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCmHUZLsuGvNUlCiaZ83jS9f49S0plAtCH19Z2iATOYPH1XE2T8ULcHdFX2GkYiaEqI+fCf1J1opif45sW/5yeDtIp4BfRAdOu2tOvkKvzlnGZndnLzFKuFfBPcysKyrGxkqBvdupOdUROiSIMwPcFgEzyLHk3pQ8lzURiJNtplQ82g3aDi4wneLDK+zuIVCl+QdP/jCc0kpYyrsWKSbxi0YrdpG3E25Q4Rn9uom58c66/3h6MVlk22w7/lMYXWc5fXmyMLwyv4KndH2u3lV45UAb6cuJ6vn6wowiD9N9J1GS57m8jAKaQC1ZVgcZBbDXMR8fbGdc9AH044JVtXe3lT shardtest@test.mongo' | tee -a ~/.ssh/authorized_keys

fio --directory=/media/ephemeral0 --name fio_test_file --direct=1 --rw=randwrite --bs=16k --size=1G --numjobs=16 --time_based --runtime=60 --group_reporting --norandommap
fio --directory=/media/ephemeral1 --name fio_test_file --direct=1 --rw=randwrite --bs=16k --size=1G --numjobs=16 --time_based --runtime=60 --group_reporting --norandommap

rm ./*.tgz || true
rm ./*.rpm || true
ls
exit 0

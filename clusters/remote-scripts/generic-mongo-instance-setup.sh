#!/bin/bash

sudo yum -y -q install tmux git wget sysstat dstat perf

dev=/dev/xvdc; sudo umount $dev; sudo mkfs.xfs -f $dev; sudo mount $dev
sudo chmod 777 /media/ephemeral0
sudo chown ec2-user /media/ephemeral0

# provision ephermeral1 for journal
dev=/dev/xvdd
readonly dpath=/media/ephemeral1
sudo mkdir -p ${dpath}
sudo umount $dev
sudo mkfs.xfs -f $dev
sudo mount $dev $dpath
sudo chmod 777 /media/ephemeral1
sudo chown ec2-user /media/ephemeral1

ln -s /media/ephemeral0 ~/data
ln -s /media/ephemeral1 ~/journal

echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
echo f | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus
echo f0 | sudo tee /sys/class/net/eth0/queues/tx-0/xps_cpus

# set ulimit nofile for ec2-user
echo "ec2-user           soft    nofile          10000" | sudo tee -a /etc/security/limits.conf
echo "ec2-user           hard    nofile          63536" | sudo tee -a /etc/security/limits.conf

echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCmHUZLsuGvNUlCiaZ83jS9f49S0plAtCH19Z2iATOYPH1XE2T8ULcHdFX2GkYiaEqI+fCf1J1opif45sW/5yeDtIp4BfRAdOu2tOvkKvzlnGZndnLzFKuFfBPcysKyrGxkqBvdupOdUROiSIMwPcFgEzyLHk3pQ8lzURiJNtplQ82g3aDi4wneLDK+zuIVCl+QdP/jCc0kpYyrsWKSbxi0YrdpG3E25Q4Rn9uom58c66/3h6MVlk22w7/lMYXWc5fXmyMLwyv4KndH2u3lV45UAb6cuJ6vn6wowiD9N9J1GS57m8jAKaQC1ZVgcZBbDXMR8fbGdc9AH044JVtXe3lT shardtest@test.mongo' | tee -a ~/.ssh/authorized_keys
chmod 400 ~/.ssh/id_rsa
rm ~/*.tgz || true
rm ~/*.rpm || true
ls
exit 0

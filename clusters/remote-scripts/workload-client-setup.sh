#!/bin/bash

sudo yum -y -q install tmux git wget sysstat dstat perf

curl -O --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/java/jdk-7u71-linux-x64.rpm; sudo rpm -i jdk-7u71-linux-x64.rpm;
sudo /usr/sbin/alternatives --install /usr/bin/java java /usr/java/jdk1.7.0_71/bin/java 20000
curl -O --retry 10 https://oss.sonatype.org/content/repositories/releases/org/mongodb/mongo-java-driver/3.2.2/mongo-java-driver-3.2.2.jar
echo 'export CLASSPATH=~/mongo-java-driver-3.2.2.jar:$CLASSPATH' >> ~/.bashrc

curl --retry 10 https://s3-us-west-2.amazonaws.com/dsi-donot-remove/utils/install_maven.sh | sudo bash

echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
echo 'never' | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
echo f | sudo tee /sys/class/net/eth0/queues/rx-0/rps_cpus
echo f0 | sudo tee /sys/class/net/eth0/queues/tx-0/xps_cpus

# set ulimit nofile for ec2-user
echo "ec2-user           soft    nofile          10000" | sudo tee -a /etc/security/limits.conf
echo "ec2-user           hard    nofile          63536" | sudo tee -a /etc/security/limits.conf

# Python dependencies for custom workloads
sudo pip install argparse python-dateutil pytz

echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCmHUZLsuGvNUlCiaZ83jS9f49S0plAtCH19Z2iATOYPH1XE2T8ULcHdFX2GkYiaEqI+fCf1J1opif45sW/5yeDtIp4BfRAdOu2tOvkKvzlnGZndnLzFKuFfBPcysKyrGxkqBvdupOdUROiSIMwPcFgEzyLHk3pQ8lzURiJNtplQ82g3aDi4wneLDK+zuIVCl+QdP/jCc0kpYyrsWKSbxi0YrdpG3E25Q4Rn9uom58c66/3h6MVlk22w7/lMYXWc5fXmyMLwyv4KndH2u3lV45UAb6cuJ6vn6wowiD9N9J1GS57m8jAKaQC1ZVgcZBbDXMR8fbGdc9AH044JVtXe3lT shardtest@test.mongo' | tee -a ~/.ssh/authorized_keys
chmod 400 ~/.ssh/id_rsa
rm ~/*.tgz || true
rm ~/*.rpm || true
ls
exit 0

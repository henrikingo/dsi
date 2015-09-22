#!/bin/bash

source setting.sh

# need make sure we checked out 10gen/workloads repo first
rm -rf ./workloads
rm -f workloads.tar.gz
git clone git@github.com:10gen/workloads.git
tar cvf workloads.tar ./workloads 
gzip workloads.tar

ssh -T -A -i $PEMFILE $SSHUSER@$mc rm -rf workloads*

scp -i $PEMFILE  ./workloads.tar.gz $SSHUSER@$mc:.

ssh -T -i $PEMFILE $SSHUSER@$mc "tar zxvf workloads.tar.gz; pwd; ls workloads/*"

# also need get the proper mongo shell to run the test
# based on discussion, we will use bundle mongoshell, 
# which is already setup, so skip this for now until we 
# feel want to change the shell. 
# ssh -T -i $PEMFILE $SSHUSER@$mc  "rm -rf 3.1.7; rm -rf bin; mkdir -p 3.1.7; mkdir -p bin; curl https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-3.1.7.tgz | tar zxv -C 3.1.7; cd 3.1.7; mv */bin .; cd ../bin; ln -s ../3.1.7/bin/mongo mongo"

MC_MONITOR_INTERVAL=1 ../../bin/mc -config run-benchRun.json -run benchRun-run -o perf.json

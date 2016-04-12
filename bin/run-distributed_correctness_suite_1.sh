#!/bin/bash

BINDIR=$(dirname $0)
source setting.sh


# need make sure we checked out 10gen/workloads repo first
rm -rf ./workloads
rm -f workloads.tar.gz
git clone git@github.com:10gen/workloads.git
tar cvf workloads.tar ./workloads 
gzip workloads.tar

ssh -oStrictHostKeyChecking=no -T -A -i $PEMFILE $SSHUSER@$mc rm -rf workloads*

scp -oStrictHostKeyChecking=no -i $PEMFILE  ./workloads.tar.gz $SSHUSER@$mc:.

ssh -oStrictHostKeyChecking=no -T -i $PEMFILE $SSHUSER@$mc "tar zxvf workloads.tar.gz; pwd; ls workloads/*"

# the current test using bundled shell, if need, we can use following line
# to speficy a particular version of shell
# ssh -T -i $PEMFILE $SSHUSER@$mc  "rm -rf 3.1.7; rm -rf bin; mkdir -p 3.1.7; mkdir -p bin; curl https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-3.1.7.tgz | tar zxv -C 3.1.7; cd 3.1.7; mv */bin .; cd ../bin; ln -s ../3.1.7/bin/mongo mongo"

MC_MONITOR_INTERVAL=1 ${BINDIR}/mc -config run-benchRun.json -run benchRun-run -o perf.json

rm -f ../perf.json
chmod 766 perf.json
cp ./perf.json ..

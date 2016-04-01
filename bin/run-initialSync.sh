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

MC_MONITOR_INTERVAL=1 ${BINDIR}/bin/mc -config run-initialSync.json -run initialSync-run -o perf.json

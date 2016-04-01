#!/bin/bash

CLUSTER=$3
BINDIR=$(dirname $0)

if [ $CLUSTER == "longevity" ]
then
    MC_PER_THREAD_STATS="no" MC_MONITOR_INTERVAL=10 ${BINDIR}/bin/mc -config run-ycsb.json -run ycsb-run-longevity -o perf.json
else
    MC_MONITOR_INTERVAL=1 ${BINDIR}/bin/mc -config run-ycsb.json -run ycsb-run -o perf.json
fi

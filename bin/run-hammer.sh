#!/bin/bash

STORAGE_ENGINE=$1
CLUSTER=$3

BINDIR=$(dirname $0)

MC_MONITOR_INTERVAL=1 ${BINDIR}/bin/mc -config hammer.json -run hammer-run -o perf.json

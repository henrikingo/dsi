#!/bin/bash

MC=${MC:-"../../bin/mc"}
MC_MONITOR_INTERVAL=1 $MC -config run-ycsb.json -run ycsb-run -o perf.json

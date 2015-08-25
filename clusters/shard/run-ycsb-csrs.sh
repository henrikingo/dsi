#!/bin/bash

MC_MONITOR_INTERVAL=1 ../../bin/mc -config run-ycsb-csrs.json -run ycsb-run -o perf.json

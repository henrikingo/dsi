#!/bin/bash

MC_PER_THREAD_STATS="no" MC_MONITOR_INTERVAL=10 ../../bin/mc -config run-ycsb.json -run ycsb-run-longevity -o perf.json

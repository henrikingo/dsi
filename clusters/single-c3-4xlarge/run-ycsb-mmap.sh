#!/bin/bash

MC_MONITOR_INTERVAL=1 ../../bin/mc -config run-ycsb-mmap.json -run ycsb-run -o perf.json

#!/bin/bash

# Runs a canned test against post_run_check.py

python ../post_run_check.py --rev 0ff97139df609ae1847da9bfb25c35d209e0936e -f core_workloads_wt.history.json -t linux-standalone.core_workloads_WT.tags.json --refTag 3.2.1-Baseline --overrideFile system_perf_override.json --project_id sys-perf --task_name core_workloads_WT --variant linux-standalone > post_run_check.out 2> post_run_check.err

failed=0

diff post_run_check.out reference/post_run_check.out.ok
if [ $? -ne 0 ]; then
    echo "Error in post_run_check.py stdout output."
    failed+=1
fi
diff post_run_check.err reference/post_run_check.err.ok
if [ $? -ne 0 ]; then
    echo "Error in post_run_check.py stderr output."
    failed+=1
fi
diff report.json reference/post_run_check.report.json.ok
if [ $? -ne 0 ]; then
    echo "Error in post_run_check.py report.json output."
    failed+=1
fi

exit $failed

#!/bin/bash

# Runs a canned test against dashboard_gen.py

python ../dashboard_gen.py --rev 0ff97139df609ae1847da9bfb25c35d209e0936e -f core_workloads_wt.history.json -t linux-standalone.core_workloads_WT.tags.json --refTag 3.2.1-Baseline --overrideFile system_perf_override.json --project_id sys-perf --task_name core_workloads_WT --variant linux-standalone > dashboard_gen.out 2> dashboard_gen.err

failed=0

echo "Testing dashboard_gen.py"
diff dashboard_gen.out reference/dashboard_gen.out.ok
if [ $? -ne 0 ]; then
    echo "Error in dashboard_gen.py stdout output."
    ((failed++))
fi
diff dashboard_gen.err reference/dashboard_gen.err.ok
if [ $? -ne 0 ]; then
    echo "Error in dashboard_gen.py stderr output."
    ((failed++))
fi
diff dashboard.json reference/dashboard_gen.dashboard.json.ok
if [ $? -ne 0 ]; then
    echo "Error in dashboard_gen.py report.json output."
    ((failed++))
fi

if [ $failed -eq 0 ]; then
    echo "test_dashboard_gen.sh completed without errors. Pass"
else
    echo "$failed tests failed in test_dashboard_gen.sh"
fi

exit $failed

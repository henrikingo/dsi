#!/bin/bash

# Run all tests

failed=0

BUILDDIR=$(dirname $0)
BASEDIR=$(dirname $(dirname $0))
cd ${BASEDIR}/analysis

python util.py # Doc test util.py
if [ $? -ne 0 ]; then
    failed+=1
fi

cd testcases
bash test_perf_regression_check.sh
if [ $? -ne 0 ]; then
    failed+=1
fi
bash test_post_run_check.sh
if [ $? -ne 0 ]; then
    failed+=1
fi
# bash test_update_overrides.sh
# if [ $? -ne 0 ]; then
#     failed+=1
# fi

if [ $failed -eq 0 ]; then
    echo "All tests passed"
else
    echo "Tests Failed! Failing tests: $failed"
fi

exit $failed

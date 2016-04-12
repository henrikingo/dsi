#!/bin/bash

# Run all tests

failed=0

BUILDDIR=$(dirname $0)
BASEDIR=$(dirname $(dirname $0))
cd ${BASEDIR}/analysis

python -m doctest -v util.py # Doc test util.py
if [ $? -ne 0 ]; then
    ((failed++))
fi

python -m doctest -v evergreen/override.py # Doc test util.py
if [ $? -ne 0 ]; then
    ((failed++))
fi

cd testcases
bash test_perf_regression_check.sh
if [ $? -ne 0 ]; then
    ((failed++))
fi
bash test_post_run_check.sh
if [ $? -ne 0 ]; then
    ((failed++))
fi
# bash test_update_overrides.sh
# if [ $? -ne 0 ]; then
#     ((failed++))
# fi

bash test_get_override_tickets.sh
if [ $? -ne 0 ]; then
    ((failed++))
fi
if [ $failed -eq 0 ]; then
    echo "All tests passed"
else
    echo "Tests Failed! Failing tests: $failed"
fi

exit $failed

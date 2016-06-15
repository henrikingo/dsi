#!/bin/bash

# Run all tests

failed=0

BUILDDIR=$(dirname $0)
BASEDIR=$(dirname $(dirname $0))

function run_test {
    "$@"
    if [ $? -ne 0 ]; then
        ((failed++))
    fi
}

pushd .
cd ${BASEDIR}/analysis

cd testcases
run_test bash test_perf_regression_check.sh
run_test bash test_post_run_check.sh
run_test bash test_dashboard_gen.sh
run_test bash test_update_overrides.sh
run_test bash test_get_override_tickets.sh
run_test bash test_delete_overrides.sh
run_test bash test_compare.sh

# run test under ./bin
popd
pwd
pip install nose
run_test nosetests -v --with-doctest --exe --ignore-files=timeseries.py . analysis

for file in $(find analysis -name "*.py"); do
    pylint --disable=locally-disabled,fixme  --reports=n $file
    if [ $? -ne 0 ]; then
        ((failed++))
    fi
done

if [ $failed -eq 0 ]; then
    echo "All tests passed"
else
    echo "Tests Failed! Failing tests: $failed"
fi

exit $failed

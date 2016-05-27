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

run_test ${BASEDIR}/testscripts/test_mongodb_setup.py

pushd .
cd ${BASEDIR}/bin
run_test python -m doctest -v setup_work_env.py  # Doc test util.py
cd ..
cd ${BASEDIR}/analysis

run_test python -m doctest -v util.py # Doc test util.py
run_test python -m doctest -v evergreen/override.py # Doc test util.py

cd testcases
run_test bash test_perf_regression_check.sh
run_test bash test_post_run_check.sh
#run_test bash test_update_overrides.sh
run_test bash test_get_override_tickets.sh
run_test bash test_delete_overrides.sh

# run test under ./bin
popd
pwd
cd ${BASEDIR}/bin
run_test python -m doctest -v  filter_bad_instance.py
pip install nose
run_test nosetests -v

if [ $failed -eq 0 ]; then
    echo "All tests passed"
else
    echo "Tests Failed! Failing tests: $failed"
fi

exit $failed

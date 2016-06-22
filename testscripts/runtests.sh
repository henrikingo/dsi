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

if [ "$github_token" != "" ]; then
    echo "Using github token."
fi

for file in v3.2/*.json v3.0/*.json master/*.json; do
    cmd_str="python validate_override_file.py $file"
    if [ "$perf_jira_user" != "" ] && [ "$perf_jira_pw" != "" ]; then
        echo "Using Jira credentials."
        cmd_str="$cmd_str --jira-user $perf_jira_user --jira-password $perf_jira_pw"
    fi
    run_test $cmd_str
done

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
    run_test pylint --disable=locally-disabled,fixme  --reports=n $file
done

if [ $failed -eq 0 ]; then
    echo "All tests passed"
else
    echo "Tests Failed! Failing tests: $failed"
fi

exit $failed

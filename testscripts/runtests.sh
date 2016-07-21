#!/bin/bash

# Run all tests
if ! [ -f config.yml ]; then
    echo "The tests require an evergreen/github config file called config.yml in the repo root."
    echo "See /example_config.yml for an example."
    exit 1
fi

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

for file in v3.2/*.json v3.0/*.json master/*.json; do
    cmd_str="python validate_override_file.py $file"
    if [ "$perf_jira_user" != "" ] && [ "$perf_jira_pw" != "" ]; then
        echo "Using Jira credentials."
        cmd_str="$cmd_str --jira-user $perf_jira_user --jira-password $perf_jira_pw"
    fi
    run_test $cmd_str
done

popd
pwd

# Explicit list of files in bin to lint until all files pass lint. 
python_to_lint=(
    bin/config_test_control.py
    bin/update_test_list.py
  )

run_test pylint --rcfile=pylintrc $(find analysis tests -name "*.py" ! -name "readers.py") ${python_to_lint[*]}
PYTHONPATH=analysis run_test nosetests -v --with-doctest --exe --ignore-files=timeseries.py --ignore-files=update_test_list.py --stop

if [ $failed -eq 0 ]; then
    echo "All tests passed"
else
    echo "Tests Failed! Failing tests: $failed"
fi

exit $failed

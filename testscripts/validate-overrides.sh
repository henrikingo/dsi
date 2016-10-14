#!/bin/bash

BUILDIR=$(dirname $0)
BASEDIR=$(dirname $(dirname $0))

source ${BUILDIR}/test-common.sh

failed=0
cmd_str="${BUILDIR}/validate_json_sorted.py"
run_test $cmd_str

cd ${BASEDIR}/analysis

# Actual override files
testfiles=$(ls */*.json)
for file in $testfiles; do
    cmd_str="python validate_override_file.py $file"
    if [ "$perf_jira_user" != "" ] && [ "$perf_jira_pw" != "" ]; then
        echo "Using Jira credentials."
        cmd_str="$cmd_str --jira-user $perf_jira_user --jira-password $perf_jira_pw"
    fi
    run_test $cmd_str
done

# Also validate files used for unittests

# This validates both input and output override files. Unfortunately output files still require
# more work. See PERF-755 for tracking.
#testfiles+=" $(ls ../tests/unittest-files/*.json*| grep -v dashboard | grep -v tags | grep -v history | grep -v revisions | grep -v report)"

# This only validates the input override files
testfiles=" $(ls ../tests/unittest-files/*.json| grep -v dashboard | grep -v tags | grep -v history | grep -v revisions | grep -v report)"

# Echo: Tickets in the unittest files don't need to actually exist in Jira
for file in $testfiles; do
    cmd_str="python validate_override_file.py $file"
    run_test $cmd_str
done


exit $failed

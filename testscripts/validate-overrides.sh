#!/bin/bash

BUILDIR=$(dirname $0)
BASEDIR=$(dirname $(dirname $0))

source ${BUILDIR}/test-common.sh

cd ${BASEDIR}/analysis

failed=0
for file in v3.2/*.json v3.0/*.json master/*.json; do
    cmd_str="python validate_override_file.py $file"
    if [ "$perf_jira_user" != "" ] && [ "$perf_jira_pw" != "" ]; then
        echo "Using Jira credentials."
        cmd_str="$cmd_str --jira-user $perf_jira_user --jira-password $perf_jira_pw"
    fi
    run_test $cmd_str
done

exit $failed

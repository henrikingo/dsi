#!/bin/bash

BUILDIR=$(dirname $0)

source ${BUILDIR}/test-common.sh

failed=0

run_test ${BUILDIR}/validate-overrides.sh
run_test ${BUILDIR}/check_format_python.py
run_test ${BUILDIR}/lint-python.sh
run_test ${BUILDIR}/lint-yml.sh
run_test ${BUILDIR}/run-nosetest.sh

if [ $failed -eq 0 ]; then
    echo "All tests passed"
else
    echo "Tests Failed! Failing tests: $failed"
fi
exit $failed

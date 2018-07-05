#!/bin/bash

BUILDIR=$(dirname $0)
source ${BUILDIR}/test-common.sh

#yamllint linting
CMD="yamllint $(find . -name '*.yml' ! -path './tests/unittest-files/perf.yml' ! -path './tests/unittest-files/system_perf.yml' ! -path './tests/unittest-files/valid_evergreen.yml') .yamllint"

failed=0

echo "Linting yaml files"
echo $CMD
run_test $CMD


#config file linting
FILES="$(find ./configurations -name '*.yml')"
echo $FILES


for I in $FILES; do
    run_test python ./bin/common/config.py "$I"
done

exit $failed

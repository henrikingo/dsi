#!/bin/bash

BUILDIR=$(dirname $0)
source ${BUILDIR}/test-common.sh

#yamllint linting
CMD="yamllint $(find . -name '*.yml' ! -path './bin/tests/unittest-files/perf.yml' ! -path './bin/tests/unittest-files/system_perf.yml' ! -path './tests/unittest-files/valid_evergreen.yml' ! -path './bin/tests/unittest-files/config_test_control/workloads.yml' ! -path './atlas/system_perf_atlas.yml') .yamllint"
failed=0

echo "Linting yaml files"
echo $CMD
run_test $CMD


#config file linting
FILES="$(find ./configurations -name '*.yml')"
echo $FILES


for I in $FILES; do
    if [ "$I" != "./configurations/baseline_config.yml" ]; then
        run_test python ./bin/common/config.py "$I"
    fi
done

echo "Yaml files that failed linting: $failed"
exit $failed

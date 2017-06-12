#!/bin/bash

CMD="yamllint $(find . -name '*.yml' ! -path './tests/unittest-files/perf.yml' ! -path './tests/unittest-files/system_perf.yml' ! -path './tests/unittest-files/valid_evergreen.yml')"

echo "Linting yaml files"
echo $CMD
$CMD

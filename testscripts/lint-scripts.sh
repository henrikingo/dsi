#!/bin/bash

BUILDIR=$(dirname $0)
source ${BUILDIR}/test-common.sh

CMD="pylint --rcfile=pylintrc $(find analysis tests bin -name '*.py' ! -name 'readers.py' ! -name 'timeseries.py')"

echo "Linting scripts"
echo $CMD
$CMD

#!/bin/bash

BUILDIR=$(dirname $0)
source ${BUILDIR}/test-common.sh

echo "Linting scripts"
echo pylint --rcfile=pylintrc $(find analysis tests bin -name "*.py" ! -name "readers.py" ! -name "timeseries.py")
pylint --rcfile=pylintrc $(find analysis tests bin -name "*.py" ! -name "readers.py" ! -name "timeseries.py")

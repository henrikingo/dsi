#!/bin/bash

CMD="pylint --rcfile=pylintrc $(find analysis tests bin -name '*.py' ! -name 'readers.py' ! -name 'timeseries.py')"

echo "Linting scripts"
echo $CMD
$CMD

#!/bin/bash

CMD="pylint --rcfile=pylintrc $(find setup.py analysis tests bin aws_tools -name '*.py' ! -name 'readers.py')"

echo "Linting scripts"
echo $CMD
$CMD

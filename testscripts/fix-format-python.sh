#!/bin/bash

CMD="yapf -i --style .style.yapf $(find analysis tests bin -name '*.py' ! -name 'readers.py')"

echo "Formatting python scripts"
$CMD

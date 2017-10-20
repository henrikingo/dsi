#!/bin/bash

CMD="yapf -i --style .style.yapf $(find analysis tests bin -name '*.py' ! -name 'readers.py' ! -name 'timeseries.py')"

echo "Formatting python scripts"
$CMD

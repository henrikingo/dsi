#!/bin/bash

CMD="yapf -i --style .style.yapf $(find analysis tests bin signal_processing -name '*.py' ! -name 'readers.py')"

echo "Formatting python scripts"
$CMD

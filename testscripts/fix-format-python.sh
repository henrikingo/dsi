#!/bin/bash

CMD="yapf -i --style .style.yapf $(find bin test_lib -name '*.py' ! -name 'readers.py')"

echo "Formatting python scripts"
$CMD

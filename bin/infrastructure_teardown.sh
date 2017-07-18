#!/bin/bash

python $(dirname $0)/infrastructure_teardown.py
rc=$?
echo "WARNING: infrastructure_teardown.sh is deprecated!"
echo "Please use infrastructure_teardown.py instead!"
exit $rc

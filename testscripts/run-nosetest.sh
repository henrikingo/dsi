#!/bin/bash

BUILDIR=$(dirname $0)
source ${BUILDIR}/test-common.sh

PYTHONPATH=analysis:bin nosetests -v --with-doctest --exe --ignore-files=timeseries.py --ignore-files=update_test_list.py --stop --logging-clear-handlers

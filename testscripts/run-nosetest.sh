#!/bin/bash

BUILDIR=$(dirname $0)
source ${BUILDIR}/test-common.sh

COVER_PACKAGES="aws_tools bin"
COVERAGE="--with-coverage --cover-inclusive --cover-xml --cover-xml-file=coverage.xml"

for package in $COVER_PACKAGES
do
  COVERAGE="$COVERAGE --cover-package=$package"
done

# use NOSE_NOCAPTURE=1 or --nocapture to view standard out
PYTHONPATH=analysis:bin nosetests  -v --ignore-files multi_graphs.py --exe $COVERAGE --logging-clear-handlers $@

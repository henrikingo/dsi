#!/bin/bash

BUILDIR=$(dirname $0)
source ${BUILDIR}/test-common.sh

COVER_PACKAGES="analysis aws_tools bin"
COVERAGE="--with-coverage --cover-inclusive  --cover-xml --cover-xml-file=coverage.xml"
for package in $COVER_PACKAGES
do
  COVERAGE="$COVERAGE --cover-package=$package"
done

PYTHONPATH=analysis:bin nosetests -v --exe $COVERAGE --logging-clear-handlers $@

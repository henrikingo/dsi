#!/bin/bash

# To destroy a cluster in the current folder.
cd `dirname $0`
TERRAFORM="${TERRAFORM:-./terraform}"
VARFILE=""
if [ -e cluster.json ]
then
    VARFILE="--var-file=cluster.json"
fi
yes yes | $TERRAFORM destroy $VARFILE

if [ $? != 0 ]
then
    # Something maybe wrong, try again
    yes yes | $TERRAFORM destroy $VARFILE
fi

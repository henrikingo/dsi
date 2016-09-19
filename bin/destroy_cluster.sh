#!/bin/bash

# To destroy a cluster in the current folder.
cd `dirname $0`
TERRAFORM="${TERRAFORM:-./terraform}"
yes yes | $TERRAFORM destroy

if [ $? != 0 ]
then
    # Something maybe wrong, try again
    yes yes | $TERRAFORM destroy
fi

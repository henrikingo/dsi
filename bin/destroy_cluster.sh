#!/bin/bash

# To destroy a cluster in the current folder. Require terraform installed under the same folder

yes yes | ./terraform destroy

if [ $? != 0 ]
then
    # Something maybe wrong, try again
    yes yes | ./terraform destroy
fi

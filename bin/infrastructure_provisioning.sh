#!/bin/bash

if [ -e ./venv/bin/activate ]; then
    source ./venv/bin/activate
fi
python $DSI_PATH/bin/infrastructure_provisioning.py
echo "WARNING: infrastructure_provisioning.sh is deprecated!"
echo "Please use infrastructure_provisioning.py instead!"

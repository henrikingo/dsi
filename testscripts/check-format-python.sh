#!/bin/bash

# Install Python3 virtualenv if it doesn't exist needed for black
export PATH=/opt/mongodbtoolchain/v3/bin:$PATH

if [[ ! -d "${DIR}/python3_venv" ]]; then
    python3 -m venv python3_venv;
    source python3_venv/bin/activate;
    python3 -m pip install black;
fi

source python3_venv/bin/activate;

black -l 100 --target-version py27 --check aws_tools dsi

deactivate

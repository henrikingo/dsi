#!/bin/bash

set -e
set -v

# install terraform
mkdir keys
mkdir terraform
cd terraform
wget -nv --no-check-certificate https://github.com/rzh/dsi/releases/download/t0.5.3/terraform_0.5.3.tar.gz -O - | tar zxv

# install workload wrapper
cd ../bin
wget -nv --no-check-certificate https://github.com/rzh/mc/releases/download/r0.0.1/mc.tar.gz -O - | tar zxv
cd ..
ls

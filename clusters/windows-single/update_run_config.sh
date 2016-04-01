#!/bin/bash

source setting.sh

sed -i -- "s/%%P1%%/\"$SSHUSER_WIN@$p1\"/g" *.json
sed -i -- "s/%%I1%%/$i1/g" *.json
sed -i -- "s/%%CLIENT%%/\"$SSHUSER_LINUX@$mc\"/g" *.json

#!/bin/bash

source ../../bin/setting.sh

sed -i -- "s/%%P1%%/\"$SSHUSER@$p1\"/g" *.json
sed -i -- "s/%%I1%%/$i1/g" *.json
sed -i -- "s/%%CLIENT%%/\"$SSHUSER@$mc\"/g" *.json
sed -i -- "s/%%ALLMEMBERS%%/\"$SSHUSER@$p1\", \"$SSHUSER@$p2\", \"$SSHUSER@$p3\"/g" *.json

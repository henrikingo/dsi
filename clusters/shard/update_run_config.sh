#!/bin/bash

source setting.sh

sed -i -- "s/%%MS%%/\"$SSHUSER@$ms\"/g" *.json
sed -i -- "s/%%ALLMEMBERS%%/\"$SSHUSER@$p1\", \"$SSHUSER@$p2\"/g" *.json
sed -i -- "s/%%MS_PRIVATE_IP%%/$ms_private_ip/g" *.json
sed -i -- "s/%%CLIENT%%/\"$SSHUSER@$mc\"/g" *.json

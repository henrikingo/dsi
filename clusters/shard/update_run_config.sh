#!/bin/bash

source setting.sh

sed -i -- "s/%%MS%%/\"$SSHUSER@$ms\"/g" *.json
sed -i -- "s/%%ALLMEMBERS%%/\"$SSHUSER@$p1\", \"$SSHUSER@$p2\", \"$SSHUSER@$p3\", \"$SSHUSER@$p4\", \"$SSHUSER@$p5\", \"$SSHUSER@$p6\", \"$SSHUSER@$p7\", \"$SSHUSER@$p8\", \"$SSHUSER@$p9\"/g" *.json
sed -i -- "s/%%MS_PRIVATE_IP%%/$ms_private_ip/g" *.json
sed -i -- "s/%%CLIENT%%/\"$SSHUSER@$mc\"/g" *.json

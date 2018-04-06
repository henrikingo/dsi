#!/usr/bin/env sh

set -e

HOSTNAME=$1

scp -o StrictHostKeyChecking=no fio.ini ${HOSTNAME}:./
ssh -A ${HOSTNAME} "mkdir -p ./data/fio && fio --output-format=json --output=fio.json fio.ini"
scp ${HOSTNAME}:./fio.json .
ssh -A ${HOSTNAME} "tar czvf fio_results.tgz fio*.log"
scp ${HOSTNAME}:./fio_results.tgz .
ssh -A ${HOSTNAME} "rm -r data/fio fio_results.tgz fio*.log"
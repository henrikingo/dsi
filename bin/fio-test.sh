#!/usr/bin/env sh

set -e

HOSTNAME=$1

ATLAS_CLUSTER="This.is.an.Atlas.cluster.SSH.not.supported"
if [ "$HOSTNAME" == "$ATLAS_CLUSTER" ]
then
  echo "Detected Atlas cluster, skipping fio."
  exit 0
fi

scp -o StrictHostKeyChecking=no fio.ini ${HOSTNAME}:./
ssh -A ${HOSTNAME} "mkdir -p ./data/fio && fio --output-format=json --output=fio.json fio.ini"
scp ${HOSTNAME}:./fio.json .
ssh -A ${HOSTNAME} "tar czvf fio_results.tgz fio*.log"
scp ${HOSTNAME}:./fio_results.tgz .
ssh -A ${HOSTNAME} "rm -r data/fio fio_results.tgz fio*.log"
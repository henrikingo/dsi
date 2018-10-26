#!/usr/bin/env sh

set -e

HOSTNAME=$1
THIS_HOST=$(hostname -i)

ATLAS_CLUSTER="This.is.an.Atlas.cluster.SSH.not.supported"
if [ "$HOSTNAME" == "$ATLAS_CLUSTER" ]
then
  echo "Detected Atlas cluster, skipping iperf."
  exit 0
fi


echo "Run iperf network tests between $THIS_HOST and $HOSTNAME."

sudo rm -f iperf.json
ssh -A ${HOSTNAME} "sudo killall iperf3" || true
sudo killall iperf3 || true

# Start the remote process
echo "Start the iperf listener side process"
LISTENER_CMD="sudo /usr/local/bin/iperf3 -s -p 27016 -D"
ssh -A ${HOSTNAME} "$LISTENER_CMD" &

sleep 2

echo "Start iperf client side process"
sudo /usr/local/bin/iperf3 -c ${HOSTNAME} -i 2 -t 60 -V -p 27016 -J --logfile iperf.json

echo "Clean up iperf processes"
kill %1
ssh -A ${HOSTNAME} "sudo killall iperf3" || true
sudo killall iperf3 || true

echo "Done $0"

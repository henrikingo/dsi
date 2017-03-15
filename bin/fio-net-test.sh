#!/usr/bin/env sh

set -e

HOSTNAME=$1
THIS_HOST=$(hostname -i)

echo "Run fio network tests between $THIS_HOST and $HOSTNAME."

ssh -A ${HOSTNAME} "killall netfio" || true
ssh -A ${HOSTNAME} "rm fio-net-listener.json" || true
killall netfio || true
rm fio-net.json || true

# Copy files over to the mongod primary, then start a listener process
scp -o StrictHostKeyChecking=no fio-net-listener.ini ${HOSTNAME}:./
LISTENER_CMD="./netfio --output-format=json --output=fio-net-listener.json fio-net-listener.ini"
echo "Start fio listener side..."
echo
ssh -A ${HOSTNAME} "$LISTENER_CMD" &

sleep 2


# Now run a client process on this node (the workload client)
echo "Start fio writer side..."
echo
#fio --ioengine=net --hostname=$HOSTNAME --rw=write --output-format=json --output=fio.json fio-net.ini
#fio --ioengine=net --filename=$HOSTNAME/8888 --rw=write --output-format=json --output=fio-net.json fio-net.ini
./netfio --output-format=json --output=fio-net.json fio-net.ini


echo "Kill remote listener and copy back the remote result file"
kill %1
scp ${HOSTNAME}:./fio-net-listener.json .
# cat fio-listener.json
ssh -A ${HOSTNAME} "killall netfio" || true
killall netfio || true

# Produce a perf.json file and cleanup
python process_fio_results.py --long --input-file fio-net.json fio_net

echo "Done $0"
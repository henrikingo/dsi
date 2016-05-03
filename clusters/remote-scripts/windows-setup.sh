#!/bin/bash

readonly mongourl=$1

rm -rf mongodb
mkdir mongodb
curl --retry 10 "$mongourl" | tar zxv -C mongodb
cd mongodb || exit 1
mv ./*/bin .
cd ~ || exit 1

chmod +x ~/mongodb/bin/*
mkdir -p ~/bin
ln -s ~/mongodb/bin/mongo ~/bin/mongo
DRIVE='/cygdrive/y'; until [ -d $DRIVE ]; do echo 'wait for '$DRIVE; sleep 1; done
DRIVE='/cygdrive/z'; until [ -d $DRIVE ]; do echo 'wait for '$DRIVE; sleep 1; done
cd /cygdrive/y || exit 1
fio --directory=. --name fio_test_file --direct=1 --rw=randwrite --bs=16k --size=1G --numjobs=16 --time_based --runtime=60 --group_reporting --norandommap --thread 2>&1 | tee /tmp/fio.log
echo "FIO test disk Y: done"

cd /cygdrive/z || exit 1
fio --directory=. --name fio_test_file --direct=1 --rw=randwrite --bs=16k --size=1G --numjobs=16 --time_based --runtime=60 --group_reporting --norandommap --thread 2>&1 | tee -a /tmp/fio.log
echo "FIO test disk Z: done"

echo 'provision done!'
exit 0

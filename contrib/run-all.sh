#!/bin/bash
# From Mark Callaghan
debug=$1

if [[ $debug == "yes" ]]; then
  dflags="-d"
else
  dflags=""
fi

for s in \
  infrastructure_provisioning \
  workload_setup \
  mongodb_setup \
  test_control \
  infrastructure_teardown \
; do
  echo $s at $( date )
  /usr/bin/time -o time.${s} ./bin/${s}.py $dflags 2>&1 | tee o.${s}
  pstat=${PIPESTATUS[0]}
  if [[ $pstat -ne 0 ]]; then
    echo $s failed with status :: $pstat ::
    exit $pstat
  fi
done
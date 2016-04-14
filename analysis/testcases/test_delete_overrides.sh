#!/bin/bash

# Runs a canned test against get_override_tickets.py

failed=0

function test_one {
    echo "Testing $1 with $2 $3 and ticket $4"
    python $1 -r $2 -f ${3}_override.json -d test.json $4 > delete.out 2> delete.err
    diff delete.out reference/delete.${3}.${2}.${4}.out.ok
    if [ $? -ne 0 ]; then
        echo "Error in $1 $2 stdout output."
        ((failed++))
    fi
    diff delete.err reference/delete.${3}.${2}.${4}.err.ok
    if [ $? -ne 0 ]; then
        echo "Error in $1 $2 stderr output."
        ((failed++))
    fi
    diff test.json reference/delete.${3}.${2}.${4}.json.ok
    if [ $? -ne 0 ]; then
        echo "Error in $1 $2 stderr output."
        ((failed++))
    fi
}

test_one ../delete_overrides.py all perf noise
test_one ../delete_overrides.py threshold perf PERF-443
test_one ../delete_overrides.py reference perf PERF-443

test_one ../delete_overrides.py all system_perf BF-1418
test_one ../delete_overrides.py threshold system_perf PERF-335
test_one ../delete_overrides.py reference system_perf PERF-335

if [ $failed -eq 0 ]; then
    echo "test_delete_overrides.sh completed without errors. Pass"
else
    echo "$failed tests failed in test_delete_overrides.sh"
fi

exit $failed

#!/bin/bash

# Runs a canned test against get_override_tickets.py

failed=0

function test_one {
    echo "Testing $1 with $2 $3"
    python $1 -r $2 -f ${3}_override.json > tickets.out 2> tickets.err
    diff tickets.out reference/tickets.${3}.${2}.out.ok
    if [ $? -ne 0 ]; then
        echo "Error in $1 $2 stdout output."
        ((failed++))
    fi
    diff tickets.err reference/tickets.perf.${2}.err.ok
    if [ $? -ne 0 ]; then
        echo "Error in $1 $2 stderr output."
        ((failed++))
    fi
}

test_one ../get_override_tickets.py all perf
test_one ../get_override_tickets.py threshold perf
test_one ../get_override_tickets.py reference perf

test_one ../get_override_tickets.py all system_perf
test_one ../get_override_tickets.py threshold system_perf
test_one ../get_override_tickets.py reference system_perf

if [ $failed -eq 0 ]; then
    echo "test_get_override_tickets.sh completed without errors. Pass"
else
    echo "$failed tests failed in test_get_override_tickets.sh"
fi

exit $failed

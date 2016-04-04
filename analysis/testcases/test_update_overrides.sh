#!/bin/bash

# Runs a canned test against update_overrides.py

python ../update_overrides.py  c2af7abae8d09d290d7457ab77f5a7529806b75a -p "performance" -k "query" -f perf_override.json -d test.json --verbose -t "Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$" noise > update_overrides.out 2> update_overrides.err

# Chain the two commands.
# Test the threshold override.
python ../update_overrides.py c2af7abae8d09d290d7457ab77f5a7529806b75a -p "performance" -k "query" -f test.json -d test.json --verbose -t "Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$" --threshold 0.66 --thread-threshold 0.77 test_threshold

diff update_overrides.out reference/update_overrides.out.ok
diff update_overrides.err reference/update_overrides.err.ok
diff test.json reference/update_overrides.json.ok

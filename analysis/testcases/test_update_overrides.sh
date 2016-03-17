#!/bin/bash

# Runs a canned test against update_overrides.py

python ../update_overrides.py  c2af7abae8d09d290d7457ab77f5a7529806b75a -p "performance" -k "query" -f ~/mongosrc/dsi/analysis/master/perf_override.json -d test.json --verbose -t "Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$" noise > update_overrides.out 2> update_overrides.err

diff update_overrides.out reference/update_overrides.out.ok
diff update_overrides.err reference/update_overrides.err.ok
diff test.json reference/update_overrides.json.ok

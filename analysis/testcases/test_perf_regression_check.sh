#!/bin/bash

# Runs a canned test against perf_regression_check.py. 

python ../perf_regression_check.py -f queries.history.json --rev 0ff97139df609ae1847da9bfb25c35d209e0936e -t linux-wt-standalone.query.tags.json --refTag 3.2.1-Baseline --overrideFile perf_override.json --variant linux-wt-standalone --threshold 0.10 --threadThreshold 0.15 > perf_regression.out 2> perf_regression.err

diff perf_regression.out reference/perf_regression.out.ok
diff perf_regression.err reference/perf_regression.err.ok
diff report.json reference/perf_regression.report.json.ok

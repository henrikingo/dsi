#! /bin/bash

# Tests the output of `../compare.py`.

failed=0

for test_name in core_workloads_wt industry_benchmarks_wt; do
	python ../compare.py --baseline compare.${test_name}.baseline.json --comparison compare.${test_name}.comparison.json
	diff perf.json compare.${test_name}.output.json
	rm perf.json

	if [ $? -ne 0 ]; then
		echo "Error in compare.py output"
		((failed++))
	fi
done

exit $failed

#!/bin/bash

#yamllint linting
CMD="yamllint $(find . -name '*.yml' ! -path './tests/unittest-files/perf.yml' ! -path './tests/unittest-files/system_perf.yml' ! -path './tests/unittest-files/valid_evergreen.yml') .yamllint"

echo "Linting yaml files"
echo $CMD
$CMD

#config file linting
FILES="$(find ./configurations -name '*.yml')"
echo $FILES

failed=0

for I in $FILES; do
	python ./bin/common/config.py "$I"
	if [ $? -ne 0 ]; then
		failed=$((failed + 1))
	fi
done

exit $failed

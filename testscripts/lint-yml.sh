#!/bin/bash

CMD="/opt/chef/embedded/bin/yaml-lint $(find . -name '*.yml')"

echo "Linting yaml files"
echo $CMD
$CMD

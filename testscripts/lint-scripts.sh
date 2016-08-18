#!/bin/bash

BUILDIR=$(dirname $0)
source ${BUILDIR}/test-common.sh

# Explicit list of files in bin to lint until all files pass lint.
python_to_lint=(
    bin/common/config.py
    bin/common/download_mongodb.py
    bin/tests/test_config.py
    bin/tests/test_download_mongodb.py
    bin/config_test_control.py
    bin/mongodb_setup.py
    bin/update_test_list.py
    bin/setup_work_env.py
    bin/common/terraform_config.py
    bin/common/terraform_output_parser.py
)

echo "Linting scripts"
echo pylint --rcfile=pylintrc $(find analysis tests -name "*.py" ! -name "readers.py") ${python_to_lint[*]}
pylint --rcfile=pylintrc $(find analysis tests -name "*.py" ! -name "readers.py") ${python_to_lint[*]}

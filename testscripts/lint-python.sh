#!/bin/bash
# fail early
set -eou pipefail

BUILDIR=$(dirname $0)
source ${BUILDIR}/test-common.sh

# Perform pylint with the correct pylintrc file.
# Please convert this to python if it becomes any more complex!

# Put new directories into one of the existing _paths arrays below
# Note we only do '-maxdepth 1' so subdirectories won't be traversed
# (this is how we have bin/* and bin/tests/* use different pylintrc files).

# this set of directories uses /pylintrc
top_paths=(
    .
    analysis
    analysis/evergreen
    aws_tools
    bin
    bin/common
    signal_processing
    signal_processing/commands
    signal_processing/commands/change_points
    signal_processing/commands/outliers
    signal_processing/change_points
    signal_processing/outliers
    signal_processing/keyring
)

# this set of directories uses /tests/pylintrc
test_paths=(
    bin/tests
    tests
    tests/test_evergreen
    testscripts
    signal_processing/tests
    signal_processing/keyring/tests
    signal_processing/commands/change_points/tests
    signal_processing/commands/outliers/tests
    signal_processing/change_points/tests
    signal_processing/outliers/tests
    test_lib
)

run_pylint() {
    # first arg is rcfile
    # rest is directories to call `find` on
    local rcfile="$1"
    shift
    local files=("$@")
    set -x
    # `-j N` runs N parallel pylint procs. Set N to 0 to get # of cores
    run_test pylint -j 0 --rcfile "$rcfile" \
        $(find "${files[@]}" -maxdepth 1 -name '*.py')
    set +x
}

failed=0
run_pylint pylintrc         "${top_paths[@]}"
run_pylint tests/pylintrc   "${test_paths[@]}"

exit $failed

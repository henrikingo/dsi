#!/bin/bash

# Run all tests
function run_test {
    "$@"
    if [ $? -ne 0 ]; then
        ((failed++))
        echo "DSI TEST FAILED" "$@"
    fi
}

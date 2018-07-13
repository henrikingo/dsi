#!/usr/bin/env python2.7
"""Test script to check formatting of python files. Outputs diffs in non-compliant files."""

from __future__ import print_function
import os
import re
import sys
from yapf.yapflib.yapf_api import FormatFile

def check_format(directories_to_check, files_to_skip):
    '''Check the formatting of every python file in the specified directories.

    :param list directories_to_check: list of directories to recursively look in for python files
    :param list files_to_skip: list of file names without ".py" that should be skipped by the
    formatter
    '''
    files_need_formatting = False
    diffs = []
    match_pattern = regex_match_pattern(files_to_skip)
    # We walk through given directories and subdirectories to find matching python files.
    for directory in directories_to_check:
        for root, _, file_names in os.walk(directory):
            for file_name in file_names:
                if re.search(match_pattern, file_name):
                    full_name = os.path.join(root, file_name)
                    # Documentation at https://github.com/google/yapf shows that the yapf diff
                    # output looks the same as git diff output looks. It shows the file name, path,
                    # and changed lines.
                    #
                    # diff is a tuple of:
                    #   1. diff output
                    #   2. encoding
                    #   3. bool indicating whether formatting is necessary
                    diff = FormatFile(
                        filename=full_name,
                        print_diff=True,
                        style_config='.style.yapf')
                    needs_formatting = diff[2]
                    if needs_formatting:
                        files_need_formatting = True
                        diffs.append(diff[0])

    if files_need_formatting:
        print("Python files were formatted incorrectly")
        print("Run 'testscripts/fix-format-python.sh' on your local repo")
        for diff in diffs:
            print(diff)
        sys.exit(1)

    else:
        print("Python files are formatted correctly")
        sys.exit(0)

def regex_match_pattern(files_to_skip):
    '''Create a regex string that:
         1. Matches all files with a ".py" extension EXCEPT FOR
         2. any files listed in 'files_to_skip'
    :param list files_to_skip: list of file names without ".py" that should be added to the
    negation of the regex string
    '''
    pattern = r"^(?!"
    pattern_end = r").*\.py$"

    for file_name in files_to_skip[:-1]:
        pattern += file_name
        pattern += r"|"
    pattern += files_to_skip[-1]

    return pattern + pattern_end
if __name__ == '__main__':
    DIRECTORIES_TO_CHECK = ['analysis', 'tests', 'bin', 'signal_processing']
    FILES_TO_SKIP = ['readers']
    check_format(DIRECTORIES_TO_CHECK, FILES_TO_SKIP)

#!/usr/bin/env python2.7
"""
Compare a new coverage.xml file against a previous one.

The previous coverage report is fetched from most recent completed task in Evergreen dsi project.
If this fails (e.g. due to network being unavailable), a fallback file from testscscripts/data/
is used.

Exit with non-zero if total code coverage is lower than in the previous.
"""
from __future__ import print_function

import sys
import xml.etree.ElementTree as ElementTree

def main():
    """
    Parse coverage.xml and a previous coverage.xml, and exit with error if total coverage decreased.
    """
    print()
    print("*** compare_coverage.py ***")
    exit_code = 0

    # New coverage.xml
    tree = ElementTree.parse('coverage.xml')
    root = tree.getroot()
    coverage_percent = float(root.attrib['line-rate'])

    # Baseline to compare against
    # (Phase 2 of this work will replace this part so that it fetches the latest result from
    # Evergreen instead. To have such results in Evergreen, I of course need to merge this first.
    # This static file in the repo can still be used as a fallback baseline for when Evergreen is
    # unavailable.
    tree = ElementTree.parse('testscripts/data/coverage.xml')
    root = tree.getroot()
    baseline_percent = float(root.attrib['line-rate'])

    ratio = coverage_percent/baseline_percent
    # Somehow the result isn't quite deterministic over different platforms. We allow 1% "rounding
    # error" or skew:
    if 1 - ratio > 0.01:
        decrease = (1-ratio)*100.0
        print("FAIL: Total code coverage decreased by {} %.".format(decrease))
        # TODO: In 2nd phase, add more info about where baseline came from and its value
        exit_code = 1
    else:
        print("PASS: Code coverage {:2.2} >= {:2.2}.".format(coverage_percent, baseline_percent))

    print()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
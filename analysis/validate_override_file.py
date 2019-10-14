#!/usr/bin/env python2.7
"""Script for validating override JSON files. `--help` for more."""

from __future__ import print_function
import sys
import argparse
from evergreen import override

USAGE_MESSAGE = """
Tool for validating the structure of override JSON files.

Optionally checks whether tickets actually exist in the MongoDB JIRA at http://jira.mongodb.org if
JIRA credentials are provided via `--jira-user` and `--jira-password`.
"""


def main(args):
    """All of the script logic."""

    arg_parser = argparse.ArgumentParser(description=USAGE_MESSAGE)
    arg_parser.add_argument("file", help="The path of the file to validate.")

    jira_creds_help = "Used to check if ticket names actually exist in the MongoDB JIRA server. "
    arg_parser.add_argument("--jira-user",
                            help="JIRA username. Must be specified along with --jira-password. " +
                            jira_creds_help)
    arg_parser.add_argument("--jira-password",
                            help="JIRA password. Must be specified along with --jira-user. " +
                            jira_creds_help)
    args = arg_parser.parse_args()

    j_user = args.jira_user
    j_pass = args.jira_password
    if j_user is not None and j_pass is not None:
        j_auth = (j_user, j_pass)
    elif j_user is None and j_pass is None:
        j_auth = None
    else:
        arg_parser.error("--jira-user and --jira-password must both be specified.")

    print("Validating file: " + args.file)
    override.Override("performance", override_info=args.file).validate(j_auth)
    print("Valid override file.")


if __name__ == "__main__":
    main(sys.argv[1:])

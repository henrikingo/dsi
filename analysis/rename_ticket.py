#!/usr/bin/env python2.7
"""A script for renaming tickets in an override file. Usage: `python rename_ticket.py --help`"""

import sys
import argparse
from evergreen import override


def main(args):
    """All the script logic."""

    description = __doc__
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("file_path", help="The path of the override file")
    parser.add_argument("old_ticket_name", help="The name of the ticket to rename")
    parser.add_argument("new_ticket_name", help="The new ticket name")
    args = parser.parse_args(args)

    override_obj = override.Override("", args.file_path)
    override_obj.rename_ticket(args.old_ticket_name, args.new_ticket_name)
    override_obj.save_to_file(args.file_path)


if __name__ == "__main__":
    main(sys.argv[1:])

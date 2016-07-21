"""
Module for setting up `argparse` arguments that are common across several scripts, to avoid code
duplication.
"""

def add_args(arg_parser, *args):
    """
    Set up `arg_parser` (an `argparse.ArgumentParser`) with the arguments corresponding to each of
    the arguments in *args. For instance, `add_args(parser, "log analysis")` will set up `parser`
    with the argument(s) that log analysis requires.
    """

    for arg in args:
        if arg == "log analysis":
            arg_parser.add_argument(
                "--log-analysis",
                nargs="+",
                help=(
                    "Analyze mongod.log files from the performance test runs for suspect messages. The first argument "
                    "to this flag should be a directory that'll be recursively searched for `mongod.log` files; in "
                    "evergreen this is most likely the 'reports/' directory. Optionally, if you want to only "
                    "analyze log messages generated during an actual test run, and ignore thoes from test "
                    "setup/transition phases, you can pass in the path to the performance results file "
                    "(probably perf.json) generated by a test runner as the second argument, since it contains test "
                    "timestamp data."))

        else:
            raise ValueError('"{0}" is an unrecognized argument.'.format(arg))

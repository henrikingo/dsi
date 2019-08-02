
# Change Point Detection, a CLI

The signal processing module provides a command line interface through the 'change-points' executable. This executable in turn provides a number of sub-commands (list, mark, hide, etc.) for processing change points.

Think of the 'change-points' exe as equivalent to the 'git' command line executable and 'change-points mark', 'change-points hide' as the git commands (pull / push / checkout).

### Installation

Install the change points command from the DSI repo. For pip, use the following:

    $> pip install -e .

__Note: ./signal\_processing/change-points.py cannot be invoked directly as it does not have a '\_\_main\_\_' block.__

### Invocation

Next verify the *change-points* command works. Run the following command, you should see something like the following output:

    $> change-points
    Usage: change-points [OPTIONS] COMMAND [ARGS]...

      For a list of styles see 'style sheets<https://matplotlib.org/users/style_sheets.html>'.

    Options:
      -d, --debug                     Enable debug output, you can pass multiple -ddddd etc.
      -l, --logfile TEXT              The log file to write to, defaults to None.
      -o, --out TEXT                  The location to save any files in.
      -f, --format TEXT               The format to save any files in.
      -u, --mongo-uri TEXT            MongoDB connection string. The database name comes from here too.
      -q, --queryable TEXT            Print ids as queries
      -n, --dry_run                   Don't actually run anything.
      -c, --compact / --expanded      Display objects one / line.
      --points TEXT                   The points collection name.
      --change_points TEXT            The change points collection name.
      --processed_change_points TEXT  The processed change points collection name.
      --build_failures TEXT           The build failures collection name.
      --style TEXT                    The default matplot lib style to use.
      --token-file TEXT
      --mongo-repo TEXT
      -h, --help                      Show this message and exit.

    Commands:
      compare              Compare points generated from R and python.
      compute              Compute / recompute change point(s).
      help                 Show the help message and exit.
      hide                 Hide a change point(s).
      list                 List points (defaults to change points).
      list-build-failures  Print list of build failures and their linked...
      manage               Manage the infrastructural elements of the...
      mark                 Mark change point(s) as acknowledged.This...
      update               Update an existing processed change point(s).
      visualize            *Note : this command is provided as is and is...

__Note: this lists the options common to all sub-commands.__

The *change-points hide* command is used to mark change points as hidden. Internally it creates a copy of matching documents from the *perf.change_points* collection in the *perf.processed_change_points* collection with the __processed\_type__ field set to hidden.

To see the help documentation invoke the following command:

    $> change-points hide --help
    Usage: change-points hide [OPTIONS] REVISION PROJECT [VARIANT] [TASK] [TEST] [THREAD_LEVEL]

          Hide a change point(s). This process creates a copy of a change_points (ephemeral output of the signal
          processing algorithm) in the (persistent) processed_change_point collection.

      Arguments can be string or patterns, A pattern starts with /.

      REVISION, the revision of the change point. This parameter is mandatory.
      PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/). This parameter is mandatory.
      VARIANT, the build variant or a regex.
      TASK, the task name or a regex.
      TEST, the test name or a regex.
      THREADS, the thread level or a regex.

      You can use '' in place of VARIANT, TASK, TEST, THREADS if you want to match all. See the
      examples.

      Examples:
          $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc

          # dry run on all sys-perf points for a given revision
          $> change-points hide $revision sys-perf -n

          # hide sys-perf change points
          $> change-points hide $revision sys-perf
          $> change-points hide $revision sys-perf linux-1-node-replSet
          $> change-points hide $revision sys-perf '/linux-.-node-replSet/'
          $> change-points hide $revision sys-perf revision linux-1-node-replSet \
             change_streams_latency  --exclude '/^(fio_|canary_)/'
          $> change-points hide $revision sys-perf linux-1-node-replSet change_streams_latency \
          '/^(fio_|canary_)/'

          #  hide all the revision sys-perf find_limit-useAgg 8 thread level
          $> change-points hide $revision sys-perf '' '' find_limit-useAgg 8

          #  hide all the revision sys-perf find_limit-useAgg all thread level
          $> change-points hide  $revision sys-perf '' '' find_limit-useAgg
          $> change-points hide $revision sys-perf '' '' find_limit-useAgg ''

    Options:
      --exclude TEXT  tests are excluded if this matches. It can be provided multiple times. A regex starts with a "/" char
      -h, --help      Show this message and exit.

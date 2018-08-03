# DSI: Signal Processing
This sub-directory concerns itself with the signal processing functionality. At present it is a suite of software based upon a python version of [e.divisive](https://www.rdocumentation.org/packages/ecp/versions/3.1.0/topics/e.divisive) which in itself based on [this document](https://arxiv.org/pdf/1306.4933.pdf).

## Command Line tools

The signal processing module provides a command line interface through the 'change-points' executable. This executable in turn provides a number of sub-commands (list, mark, hide ..) for processing change points.

Think of the 'change-points' exe as equivalent to the 'git' command line executable and 'change-points mark', 'change-points hide' as the git commands (pull/ push / checkout).

### Installation

Install the change points command from the DSI repo. For pip, use the following:

    $> pip install -e .

__Note: ./signal_processing/change-points,py cannot be invoked directly as it does not have a '\_\_main\_\_' block.__

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
      compare    Compare points generated from R and python.
      compute    Compute / recompute change point(s).
      help       Show the help message and exit.
      hide       Hide a change point(s).
      list       List points (defaults to change points).
      manage     Manage the infrastructural elements of the...
      mark       Mark change point(s) as acknowledged.This...
      update     Update an existing processed change point(s).
      visualize  *Note : this command is provided as is and is...

__Note: this lists the options common to all sub-commands.__

*change-points hide* command is used to mark change points as hidden. Internally it created a copy of matching  documents from *perf.change_points* collection in the *perf.processed_change_points* collection with the processed_type field set to hidden.

To see the help invoke the following command:

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

### Source Code Layout

The code for the command line tool is in '__signal_processing/change_points.py__'. Withing this file each sub-command is implemented in a function called '<subcommand>_command'. For example 'change-points mark' is implemented by the *mark_command* function. The command functions are concerned with processing the command line arguments from click and invoking the implementation in signal_processing/commands directory. In most cases there is a one to one relationship betweent the 'change-points <command name>' and the python file that implemented it. So the *mark_command* function delegates to '__signal_processing/commands/mark.py__'. Some notable exceptions are the *hide_command* which is essentially a synonym of mark with the processed_type parameter set to hidden. The other case being the *list_command* function which is implmented in '__signal_processing/commands/list_change_points.py__' as list is a builtin in python and it is a bad idea to reuse a buyiltin name. 

In addition, there is a click group implemented in a function  called 'cli'. This group processes common command line argurments for all the other comamnds (e.g. -u / --mongo-uri, -d / --debug , -l / --log-file etc) and creates a CommandConfiguration instance which is passed to each command.


## Database Infrastructure
The state is stored in an Atlas database (called perf). A number of indexes and a view are required. These database objects are described here.

### Unprocessed Change Points Collection

The *perf.unprocessed_change_points* collection is implented as a view on the *perf.change_points* collection. The view lists all change points that have not been hidden and are not already covered by a build failure.

#### Unprocessed Change Points Description

The *perf.unprocessed_change_points* collection is implented as a view on the *perf.change_points* collection. 

See [Field Descriptions](#field-descriptions) for an explanation of the documents.

The view pipeline has a number of stages:

   1. Lookup (as the __hidden_processed_change_points__ field) all documents in the *perf.processed_change_points* that match *perf.change_points* documents:
        1. __project__ field.
        1.  __variant__ field.
        1. __task__ field.
        1. __test__ field.
        1. __thread_level__ field.
        1. __suspect_revision__ field.
        1. __processed_type__ field set to '*hidden*'

    1. Filter documents with a non-empty __hidden_processed_change_points__ field from the view.

    1. Lookup (as __build_failures__ field) all docuemnts in *perf.build_failures* that match *perf.build_failures* doucments:
        1. __project__ field.
        1. any *perf.change_points* '__all_suspect_revisions__' value in __first_failing_revision__' or '__fix_revision__' *perf.build_failures* fields
    1. Filter documents with a non-empty '__build_failures__' field from the view.
    1. Remove the '__hidden_processed_change_points__' and '__build_failures__' fields with a projection.

The remaining documents need to be processed to hide them or to create a Build Failure to track the issue. 

#### Field Descriptions

Common document fields:
   1. The __project__ field contains the performance project identifier. For example, 'sys-perf', 'sys-perf-4.0', 'performance'. This field is a scalar value in all cases except *perf.build_failures* where it is an array field. A change point is generated for a single project, variant, task, test and thread_level but build failures can cover many projects (the same logical commit in different project branches).
   1. The __variant__ field contains the performance variant identifier. For example, 'linux-standalone', 'linux-1-node-replSet'.
   1. The __task__ field contains the performance task identifier. For example, 'bestbuy_agg', 'industry_benchmarks'.
   1. The __test__ field contains the performance variant identifier. For example, 'find-noAgg', 'ycsb_100read'.
   1. The __thread_level__ field contains the number of threads for a given performance result.

A change point document has the following additional relevant fields:
   1. The __suspect_revision__ field contains the githash revision of the first build that displays the change in performance. This does not mean that it is sure to be the root cause, there could be older revisions which were not yet run.
   1. The __all_suspect_revisions__ array field contains the list of revisions which could contain the commit that caused the performance change. __suspect_revision__ is included in this list.

A build failure (BF) document has the following additional relevant fields:
   1. The __first_failing_revision__ array field contains a list of revisions which are currently associated with the root cause of this BF. There can be more than one revision but each revision should be for a single unique project.
   1. The __fix_revision__ array field contains a list of revisions which are associated with the fix for this BF. There can be more than one revision per project (to cover the case where an issue is fixed in stages or incompletely).  

#### View Creation / Change

After each change, you must update the view in the database.

To create the view in Atlas, you should run the following command:

    $> sp_password=.... # you must set this
    $> change-points -u "mongodb+srv://signal_processing:${sp_password:?not set}@performancedata-g6tsc.mongodb.net/perf" manage 

OR create and test the view locally:

    $> change-points -u 'mongodb://localhost/perf' manage 

To view the help run:

    $> change-points --help        # view the group help which contains common parameters
    $> change-points manage --help # view the command help


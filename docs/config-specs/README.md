Distributed Performance 2.0 config file format specification
=============================================================

This directory contains files that serve as both an example and a
specification for the configuration files used by DSI modules, as of
Distributed Performance 2.0.

For more context, see https://docs.google.com/document/d/1QdVoSnvoqA1CBQRZNzrDFTJ7REAml3cq4bgWZi9qaPQ/edit#
These files add more detail to that high level specification.

A design goal is that these files contain the entire end-to-end configuration for a test run. For example, a subsection of mongodb_setup.yml is a valid mongod config file. The mongodb_setup module will copy that section, store it into a new file, and pass to a mongod process when deploying mongodb.

**Conventions:**
* Keys and values are generally the values mandated by this spec.
* Some values are examples only. For example the prefix "my" is used for user defined values, such as "myrs0".
* $RUNTIME_VALUE refers to a value provided at runtime by the environment.
  This is used for secret aws keys, or build/runtime specific info like mongodb binaries.
  You can usually omit such fields in real config files, they will be added by environment.
  If such a field is specified, that value will prevail, runtime value will not be added.
* ${module_name.key_name} are variables that can reference the value of another key in the 
  configuration. The library that reads the config files will automatically substitute the
  variables for their values.


Overview of files
-----------------

There's a set of files **for each module**:

* `module_name.yml`: The input configuration file for `module_name`. Note that 
  other modules can use config values from this file if needed, but the main 
  context for these config options is the module called `module_name`.
* `module_name.out.yml`: Output from a module, can be used as input by other 
   modules. For example: infrastrucutre_provisioning.out.json will contain
  an ordered list of private and public ip addresses assigned to the requested
  resources.
* `module_name.override.yml`: Optional file that can specify keys that override 
  values from the previous files. (Use case is if you want to run a test using 
  the standard set of files stored in this repo, but override one config option.
  For example: Give me a regular 3-shard cluster, but one shard should use
  inMemory engine.)

A common library will know how to read each file in the correct order and how to override values when needed. Modules will simply get/set keys in a dictionary.

Use cases and requirements
--------------------------

I've tried to think about the following use cases when designing the spec:

* Support current set of variants and tests.
  * There will be a directory with common configurations. Roughly we will need
    * for each variant a set of `infrastructure_provisioning.json`,
      `system_setup.yml` and `mongodb_setup.yml`.
    * for each dsi/clusters/*.json file a set of `workload_preparation.yml`,
      `test_control.yml` and `analysis.yml`
  * At the beginning of each evergreen task, we copy the relevant ones
    of these files into a working directory (PERF-434). This working directory 
    is what we need to cd into in system_perf.yml.
  * Note: as each module does its work, the working directory is further populated
    by .out.yml files, at most one for each module.

* Support more options than current, rather fixed set of variants
  * Support for specifying arbitrary MongoDB configuration file
  * Support for specifying arbitrary mongo shell commands
  * Support for specifying additional Terraform resources (e.g. EBS disk)
  * Etc...

* Support reconfiguration within a build.
  * For example, we already need to reconfigure mongodb cluster to use
    different storage engine. In this case you could reuse the other
    files, but provide a `mongodb_setup.override.yml` file to override
    the storage engine.
  * How exactly the implementation activates such a changed configuration, is 
    out of scope for this discussion. But a reconfiguration would again use these 
    input files.

* Support reconfigurations during a running test.
  * As a general case this is out of scope for DP2.0.
  * We only support the case like initialsync does currently, where the starting
    point is that all AWS resources exist, and mongod is installed and running
    on all servers, but some additional `rs.add()` or `sh.addShard()` commands
    can be called in the mongo shell during the test.
  * I do believe that this same configuration file spec can be used also for
    such within-test reconfigurations, but the more interesting question is
    how a test can trigger such a reconfiguration to happen. We need some kind
    of API for that.


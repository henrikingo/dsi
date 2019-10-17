# Getting Started 

## Intro
This guide goes over performance testing, covering the code used in a performance test and the lifecycle that each individual test lives through. We will particularly note the
repositories that are used. 

The big picture of system performance is as follows: Evergreen uses a project file to run a task, where each task may represent multiple tests. As part of executing this task, Evergreen will prepare a host on which DSI will be executed. When DSI is executed on this host, the DSI node itself will spin up a variety of hosts, depending on the exact task being run. Some of these hosts will contain mongod instances, while others will act as workload clients. (At the moment only a single workload client is supported.) A workload client is a node that performs some workload designed to stress the system of mongod instances. After executing, the cluster set up by the DSI node is closed down and the data stored. 

While many different hosts may be used in a given run of sys-perf, *DSI itself is only ever executed on Evergreen hosts.* Other operations, such as setting up mongod instances, are performed using SSH on nodes spun up by DSI.

### Repositories
There are several repositories that are relevant to sys-perf. They include:

  - [Evergreen](https://github.com/evergreen-ci/evergreen), which actually executes the DSI scripts.
  - [DSI](https://github.com/10gen/dsi), which contains all the test scripts needed to create clusters and perform tests on them.
  - [genny](https://github.com/mongodb/genny), which is a tool used to create workloads.
  - [workloads](https://github.com/10gen/workloads), which contains a set of JavaScript workloads for DSI clusters. Note that we are trying to transition from using these workloads to having more projects use genny. The STM team doesn't own individual workloads themselves.

These repositories are Evergreen modules defined in the system_perf.yml project file.

## Evergreen
System performance testing, or "sys-perf", is an [Evergreen project](https://evergreen.mongodb.com/waterfall/sys-perf) whose goal is detecting inabilities of the mongodb server to live up to certain performance guarantees, or to detect abrupt changes in performance. For background on Evergreen, check out the [Evergreen wiki](https://github.com/evergreen-ci/evergreen/wiki), particularly the article describing [project files](https://github.com/evergreen-ci/evergreen/wiki/Project-Files).

This project is controlled by the [etc/system_perf.yml](https://github.com/mongodb/mongo/blob/master/etc/system_perf.yml) file. Each task will execute a series of functions, which we will discuss in order. Each function assumes the previous have been executed.

### prepare environment
[This function](https://github.com/mongodb/mongo/blob/ec0bf809b1b60c4edc32146ed971222c30f9d8fa/etc/system_perf.yml#L199) does everything needed to prepare the DSI node for execution. It will download all git repositories, then output a `bootstrap.yml` that is dynamically generated to contain all the values needed for DSI to run correctly. For example, if a task specifies a certain `mongodb_setup.*.yml` file, then that file is stated in the `bootstrap.yml` file. It will also prepare the AWS secret keys. Finally, the `bootstrap.py` script in DSI is executed.

### deploy cluster 
[This function](https://github.com/mongodb/mongo/blob/ec0bf809b1b60c4edc32146ed971222c30f9d8fa/etc/system_perf.yml#L298) does everything needed to deploy the cluster of mongodb nodes and workload client. It executes the DSI scripts `infrastructure_provisioning.py`, `workload_setup.py`, and `mongodb_setup.py`.

### run test
[This function](https://github.com/mongodb/mongo/blob/ec0bf809b1b60c4edc32146ed971222c30f9d8fa/etc/system_perf.yml#L310) actually runs the test, now that the cluster has been properly established. This involves executing the `test_control.py` script of DSI.

### analyze
[This function](https://github.com/mongodb/mongo/blob/ec0bf809b1b60c4edc32146ed971222c30f9d8fa/etc/system_perf.yml#L325) detects outliers and runs regressions against past performances.

## DSI
[DSI](https://github.com/10gen/dsi), or "Distributed System Test Infrastructure", is a collection of scripts that are used by Evergreen to run performance tests. Each is executed once during the run of a single test. There can be thought to be a sequence of "modules", where each receives an input .yml file and then outputs a .yml file. The modules themselves are python scripts with names similar to the .yml files they input and output. All possible input configuration files are in the `configuration` directory of the DSI repository. At runtime, each module's python script is executed by Evergreen in sequence with the appropriate configuration present.

The stages are discussed in order.

### bootstrap.py
[This script](https://github.com/10gen/dsi/blob/master/bin/bootstrap.py) is executed by the `prepare environment` function in Evergreen. It uses the Evergreen-generated `bootstrap.yml` file to determine which configuration files are needed, and copy them into the working directory. It also prepares Terraform, the system used to set up AWS instances.

### infrastructure_provisioning.py
[This script](https://github.com/10gen/dsi/blob/master/bin/infrastructure_provisioning.py) is executed by the `deploy cluster` function in Evergreen. It uses Terraform and the local AWS keys to prepare all the EC2 instances needed by later stages.

### workload_setup.py
[This script](https://github.com/10gen/dsi/blob/master/bin/workload_setup.py) is executed by the `deploy cluster` function in Evergreen. It prepares the workload client to run tests.

### mongodb_setup.py
[This script](https://github.com/10gen/dsi/blob/master/bin/mongodb_setup.py) is executed by the `deploy cluster` function in Evergreen. It connects to each of the nodes created by `infrastructure_provisioning.py` and creates the appropriate MongoDB process, whether that's a mongod, a mongos, or config servers. It will ensure that these processes are created withe appropriate mongod configuration, and will connect replica sets, sharded clusters, and standalone instances according to the topology defined in the appropriate `mongodb_setup.*.yml`.

### test_control.py
[This script](https://github.com/10gen/dsi/blob/master/bin/test_control.py) is executed by the 'run test' function in Evergreen. It actually runs the test; connecting to the workload client and running each of the workloads described in the correct `test_control.*.yml`.


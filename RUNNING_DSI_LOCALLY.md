Running DSI Locally
===================

*Note*: This document originally lived on Google Docs [here](https://docs.google.com/document/d/14QXOmo-ia8w72pW5zqQ2fCWfXEwiVQ8_1EoMCkB4baY/edit#).

Introduction
------------

It is possible to spin up clusters identical to the ones used in the sys-perf project, and use them for testing new workloads or debugging existing issues. Setting up and running tests locally largely follows the process described in the [Basic Sys-Perf Flow] section.

  [Basic Sys-Perf Flow]: https://docs.google.com/document/d/1wnZQbuP9482TR7UP-SKEZtntdB2O2K3lE15nHc2XTpw/edit#heading=h.w0wh5f7fsj0

TL;DR (for Linux)
-----------------

```sh
# linux:
sudo apt install awscli
# mac:
brew install awscli

aws configure  # Use MANA to get credentials
# Mana: https://wiki.corp.mongodb.com/display/DEVOPSP/AWS+entitlements+in+MANA

ssh-keygen -m PEM -t rsa -b 2048 -C $(whoami)-dsikey 
     -f  ~/.ssh/$(whoami)-dsikey #no pass


# initialize ssh-agent, assuming you are using bash
ssh-agent bash

ssh-add ~/.ssh/$(whoami)-dsikey

for a in $(aws ec2 describe-regions --query 'Regions[].{Name:RegionName}' --output text); do aws ec2 import-key-pair --key-name $(whoami)-dsikey --public-key-material file://~/.ssh/$(whoami)-dsikey.pub --region $a ; done

git clone git@github.com:10gen/dsi.git
cd dsi
./run-dsi setup


# this version of terraform is only for linux
curl -o terraform.zip https://releases.hashicorp.com/terraform/0.12.16/terraform_0.12.16_linux_amd64.zip 

# for mac https://releases.hashicorp.com/terraform/0.12.16/terraform_0.12.16_darwin_amd64.zip 

sudo unzip terraform.zip -d /usr/local/bin

# if running a new Genny workload, be sure to fill in test_name and auto_genny_workload
$EDITOR configurations/bootstrap/bootstrap.example.yml

source ./dsi_venv/bin/activate

./dsi/bootstrap.py --directory WORK --bootstrap-file configurations/bootstrap/bootstrap.example.yml
cd WORK
export PATH=.bin:$PATH

../run-dsi infrastructure_provisioning.py
../run-dsi workload_setup.py
../run-dsi mongodb_setup.py
../run-dsi test_control.py
../run-dsi analysis.py
../run-dsi infrastructure_teardown.py
```

You can run these steps multiple times (e.g. run `test_control.py` multiple times) without having to run other scripts again first.

Requirements
------------

### Credentials

You will need AWS Credentials and an SSH key to locally provision a cluster.

[AWS Credentials (AWS access key and secret key -- follow instructions at this link)][]: These instructions tell you how to request an AWS IAM User and Group permissions through Mana. The AWS Account for both User and Group should be aws-kernel-test and for the group request the AWS Group should be `Kernel__EC2FullAccess_only`. When you submit these requests, leads will receive an email to approve the request. Once you have been approved, follow the last steps on the MANA Wiki page to create your access key and secret key.

Once you have been approved, you can follow [these instructions] to configure AWS.

Following the instructions from the AWS configuration above use `aws-configure` to create a `~/.aws/credentials` file, or make one manually. Enter the access key and secret key from above and leave the default region and output format blank. The file should be a text file of the form:

    [default]
    aws_access_key_id = ABCDEF...
    aws_secret_access_key = A1B2C3...

[SSH key][]:

The ssh key is a 2048-bit RSA private key which will enable you to access your AWS resources. To create a key pair, execute:

```sh
ssh-keygen -m PEM -t rsa -b 2048 -C "<NAME OF SSH KEY>"
```

This key name exists in a namespace shared with co-workers. Please include your name in the key name.

You will be prompted to enter a file to save the key in:

```sh
~/.ssh/"<NAME_OF_SSH_KEY>"
```

**DO NOT enter a passphrase. Passphrase-protected keys will not work with AWS**

This will also create a public key file:

```sh
~/.ssh/"<NAME_OF_SSH_KEY>".pub
```

You must upload the ssh public key to all regions (remove from the list any regions that already have the ssh key). You can automate that process with a script like this one:

```sh
for a in us-east-1 us-east-2 us-west-1 us-west-2 ap-south-1 ap-northeast-1 ap-southeast-1 ap-southeast-2 ap-northeast-2 eu-central-1 eu-west-1 eu-west-2 ; do aws ec2 import-key-pair --key-name NAME_OF_SSH_KEY --public-key-material file://~/.ssh/NAME_OF_SSH_KEY.pub --region $a ; done
```

To view the list of all ssh key pairs in all regions, you can run this script:

```sh
for a in us-east-1 us-east-2 us-west-1 us-west-2 ap-south-1 ap-northeast-2 ap-southeast-1 ap-southeast-2 ap-northeast-1 eu-central-1 eu-west-1 eu-west-2 ; do echo $a ; aws ec2 describe-key-pairs --region $a ; done
```

To ensure that your SSH agent has key access, execute:

```sh
ssh-add /path/to/keyfile
# (example: ssh-add ~/.ssh/my_ssh_key)
```

  [AWS Credentials (AWS access key and secret key -- follow instructions at this link)]: https://wiki.corp.mongodb.com/display/DEVOPSP/AWS+entitlements+in+MANA
  [these instructions]: https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html
  [SSH key]: https://www.ssh.com/ssh/keygen/

### Repos

Check out the required repos into an easily accessible location.

**Required**

[DSI][]:

```sh
git clone git@github.com:10gen/dsi.git
```

**Optional**

[Mongo][]:

```sh
git clone git@github.com:mongodb/mongo.git
```

[Workloads] (if you will be running custom workloads):

```sh
git clone git@github.com:10gen/workloads.git
```

[YCSB][]:

```sh
git clone git@github.com:mongodb-labs/YCSB.git
```

[Genny][]:

```sh
git clone git@github.com:mongodb/genny.git
```

  [DSI]: https://github.com/10gen/dsi
  [Mongo]: https://github.com/mongodb/mongo
  [Workloads]: https://github.com/10gen/workloads
  [YCSB]: https://github.com/mongodb-labs/YCSB
  [Genny]: https://github.com/mongodb/genny

### Dependencies

You must download binaries for Terraform:

-   Downloads
    -   [Linux]
    -   [Mac OS X]
    -   Other binaries and checksums can be found at [Other binaries and checksums]
-   You **must** have version 0.12.16, despite newer versions possibly available.
    -   Hint: `terraform version`
-   Put the terraform binary into your PATH

Make sure terraform is present in your `PATH` before proceeding to the Setup Work Directory phase.

If desired, create and activate a virtualenv to store required dependencies:

```sh
virtualenv venv; source venv/bin/activate
# or use ./run-dsi setup to setup a virtualenv in ./dsi_venv
# this does the below pip install for you.
# activate via source ./dsi_venv/bin/activate
```

To install necessary dependencies, run:

```sh
pip install -r PATH_TO_DSI/requirements.txt 
```

To escape the virtualenv, run:

```sh
deactivate
```

  [Linux]: https://releases.hashicorp.com/terraform/0.12.16/terraform_0.12.16_linux_amd64.zip
  [Mac OS X]: https://releases.hashicorp.com/terraform/0.12.16/terraform_0.12.16_darwin_amd64.zip
  [Other binaries and checksums]: https://releases.hashicorp.com/terraform/0.10.4/

Set Up Work Directory
---------------------

To set up a work directory:

```sh
cp <path_to_dsi>/configurations/bootstrap/bootstrap.example.yml bootstrap.yml

<EDITOR> bootstrap.yml #FOLLOW THE INLINE DOCUMENTATION

<path_to_dsi>/bin/bootstrap.py --directory WORK --bootstrap-file bootstrap.yml
```

`WORK` can be an arbitrary directory path of your choosing. It will be created by bootstrap.py if it doesn't already exist and the environment will be set up within it. If `--directory` is not used, the environment will be set up within the current working directory. If `--directory` was used:

```sh
cd WORK
```

The python executables you will be using are conveniently symlinked under `./.bin/`. You can call them via that path directly, or add `.bin` to your `PATH`:

```sh
export PATH=.bin:$PATH
```

At this point you have a functioning DSI working directory and can provision a cluster.

Provision Infrastructure
------------------------

NOTE: You are provisioning resources in AWS. You need to clean them up later. See below Analysis section for how to do that.

From this point forward, we assume you are in the working directory and have sourced `dsienv.sh`. To provision infrastructure, execute:

```sh
infrastructure_provisioning.py
```

This will allocate and configure your requested cluster. The input configuration for this step is in the file `infrastructure_provisioning.yml`[^1]. Information about the infrastructure that gets provisioned is located in `infrastructure_provisioning.out.yml`.

If you see an error on this step complaining about a parse error (you may see your a dump of your key file, looking something like `--- BEGIN OPENSSH ....`), that means your key file is in a format that Terraform can't read.

Here's a fix:

Navigate to the folder where you've stored your ssh keys (usually `~/.ssh`). Let's say you see the files `my_key` and `my_key.pub` there. If you run `cat my_key`, you should see the contents of your file, which is what Terraform dumped earlier.

Here, run the following command to convert your key files to a format Terraform understands (note that you need to run this command once, on the my_key file only. The command will convert both files):

```sh
ssh-keygen -p -m PEM -f ~/.ssh/my_key
```

If you run `cat my_key` you should see that the file now starts with ``--- BEGIN RSA -``. Terraform should now accept it.

[^1]: In most cases you don't need to edit these other files, just `bootstrap.yml` is enough. If you do want to tweak details of the configuration, the entire set of options that can be given via the yaml configuration files is fully documented in `$DSI_PATH/docs/config-specs/`.

Setup the workload hosts
------------------------

To setup the workloads, execute:

```sh
infrastructure_provisioning.py
```

This will setup the hosts for various kinds of workload types specified in `workload_setup.yml`. Note that the setup is only done for matching types specified in test.run.type in `test_control.py`. Note that this step only has to be run once, even if you re-deploy the mongodb cluster and rerun tests.

Deploy a Mongodb Cluster
------------------------

In the working directory, execute:

```sh
mongodb_setup.py
```

This will start a MongoDB cluster as specified in `mongodb_setup.yml`. It will download and install the binary archive specified with mongodb_binary_archive key.

To supply your own binary, such as from your Evergreen compile task, add its URL to `mongodb_setup.yml`:

```yaml
mongodb_binary_archive: http://s3.amazonaws.com/mciuploads/dsi/<patch_info>.tar.gz
```

If you want to upload your own binary (such as via SCP), then you must set this option to the empty string: `""`. In that case this step will simply start mongodb using `~/mongodb/bin/mongod` (or `mongos`)

Run Tests
---------

The tests to run are specified in `test_control.yml`. To run the tests, in the working directory, execute:

```sh
test_control.py
```

Running the tests will create a directory called `reports/` with the results from the run. It will also, by default, clone a new copy of the `workloads` repo from github, using your github SSH key, so you may be prompted for that key's passphrase. You can also specify a pre-existing `workloads` directory for `test_control.py` to use, if you've made local changes.

Connect to the Cluster
----------------------

You can simply connect to all the machines using `conn.py` from the working directory. See `infrastructure_provisioning.out.yml` for a list of all the machines that have been allocated and their ip addresses. For instance, to connect to the client machine that drives the load:

```sh
conn.py wc
```

Other targets you can connect to if desired:

-   `wc`: The client machine running the workload
-   `md.N`: Server instance `N` (for `mongod`)
-   `ms.N`: Server instance `N` (for `mongos`)
-   `cs.N`: Server instance `N` (for config servers)

Analyze Results
---------------

For performance benchmarks, the most interesting question is whether results changed significantly compared to some historical reference. This question is answered by a different piece of code that lives in [signal processing repository].

However, some static error checking is performed immediately after a test by running:

```sh
analysis.py
```

This script checks for core files, errors in `mongod.log`, and some hard limits for various FTDC metrics. It produces the `report.json` file that has pass/fail information in a format understood by Evergreen.

  [signal processing repository]: https://github.com/10gen/signal-processing

Clean Up Your Resources
-----------------------

The simplest way is to execute:

```sh
infrastructure_teardown.py
```

This will output a message confirming that your resources were destroyed:

    Destroy complete! Resources: 8 destroyed.

-   Note: The terraform state of your cluster is stored in your work directory. Don't delete the directory before you have successfully executed `infrastructure_teardown.py`
-   Note: You must run `infrastructure_teardown.py` in the work directory that you want to destroy resources for. If you run the script in the wrong directory, it won't give an error but just say that "0 resources" were destroyed.

Frequently Asked Questions
--------------------------

**It takes hours to run all the tests in a task, how can I disable some tests?**

Any tests, can be omitted by commenting or deleting them from `test_control.yml`. In particular, you may want to start with deleting the tests called `fio_`, `iperf_` and `canary_`.

By the way, you can do that for an evergreen patch build as well:

1.  Checkout a branch of dsi repo, edit your relevant yaml file.

2.  Submit your `evergreen patch -p sys-perf` job as usual

3.  In the dsi repo, submit your dsi changes:

         evergreen set-module -m dsi -i <id from output of previous row>

4.  Start (aka finalize) your patch in Evergreen UI as usual. You should see the dsi changes as part of the diff.

At the end of each test, we run some **validation checks** (that we borrowed from the correctness jstests. This can be **disabled in either of three different way**s:

-   In `test_control.yml` set the `skip_validate` option to `true` in the test run that you would like to disable the validation tests for. For an example, see [here].
-   Making sure that the configuration `test_control.jstests_dir` is set to the empty string "" Either [here][1] or in your test_control.yml file, [such as here].
-   Making sure your `mongod` binary archive doesn't contain a `jstests/` directory.

Disabling collection of `mdiag.sh` stats is a bit trickier. Edit `overrides.yml` to add the following:

```yaml
mongodb_setup:
  post_task:
    - on_all_servers:
        exec: echo "Skipping mdiag.sh"
    - on_all_servers:
        exec: echo "Not downloading mdiag files"
```

**If you see this error: `Error connecting to SSH_AUTH_SOCK: dial unix /private/tmp/com.apple.launchd.PlFE7ecIaP/Listeners: connect: no such file or directory`**

-   You need to have ssh-agent running: `ssh-agent bash` (or whatever shell you're using) and `ssh-add ~/.ssh/$(whoami)-dsikey`

**SSH key printed ``(--- BEGIN OPENSSH ...)``**

If you see an error on this step complaining about a parse error (you may see your a dump of your key file, looking something like `--- BEGIN OPENSSH ....`), that means your key file is in a format that Terraform can't read. Here's a fix:

Navigate to the folder where you've stored your ssh keys (usually `~/.ssh`). Let's say you see the files `my_key` and `my_key.pub` there. If you run `cat my_key`, you should see the contents of your file, which is what Terraform dumped earlier.

Here, run the following command to convert your key files to a format Terraform understands (note that you need to run this command once, on the `my_key` file only. The command will convert both files):

```sh
ssh-keygen -p -m PEM -f ~/.ssh/my_key
```

If you run `cat my_key` you should see that the file now starts with `--- BEGIN RSA -`. Terraform should now accept it.

**Errors in `terraform.debug.log`**

When provisioning the EC2 instances (i.e `infrastructure_provisioning.py`), if you see below error to `iam/GetUser request` in `terraform.debug.log`, then it's a harmless error.

    -----------------------------------------------------
    2019/11/20 09:52:56 [DEBUG] [aws-sdk-go] DEBUG: Response iam/GetUser Details:
    ---[ RESPONSE ]--------------------------------------
    HTTP/1.1 403 Forbidden
    Connection: close
    Content-Length: 368
    Content-Type: text/xml
    Date: Wed, 20 Nov 2019 14:52:56 GMT
    X-Amzn-Requestid: 98ca53c1-cacf-4e90-af82-76e914cba248
    <ErrorResponse xmlns="https://iam.amazonaws.com/doc/2010-05-08/">
    <Error>
    <Type>Sender</Type>
    <Code>AccessDenied</Code>
    <Message>User: arn:aws:iam::579766882180:user/Suganthi.Mani is not authorized to perform: iam:GetUser on resource: user Suganthi.Mani</Message>
    </Error>
    <RequestId>98ca53c1-cacf-4e90-af82-76e914cba248</RequestId>
    </ErrorResponse>

  [here]: https://github.com/10gen/dsi/blob/5e742b8b26bd7d590c2f9ece0f4099ef128aa6a8/configurations/test_control/test_control.crud_workloads.yml#L43
  [1]: https://github.com/10gen/dsi/blob/8efe9a3db74161ff132870227e4337de2a14d9af/configurations/defaults.yml#L145
  [such as here]: https://github.com/10gen/dsi/blob/8efe9a3db74161ff132870227e4337de2a14d9af/configurations/test_control/test_control.initialsync-logkeeper.yml#L41

# Credentials

You will need AWS API credentials and an SSH key to locally provision a cluster.

Following [the AWS documentation](http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html)
use `aws-configure` to create a `~/.aws/credentials` file, or make one manually. Enter the access
key and secret key and leave the default region and output format blank. The file should be a text file of the form:

    [default]
    aws_access_key_id = ABCDEF...
    aws_secret_access_key = A1B2C3...

## SSH key:

The ssh key is a 2048-bit RSA private key which will enable you to access your AWS resources. To
create a key pair with [ssh-keygen](https://www.ssh.com/ssh/keygen/), execute:

	ssh-keygen -m PEM -t rsa -b 2048 -C "<NAME OF SSH KEY>"
	
This key name exists in a namespace shared with co-workers. Please include your name in the key
name.

You will be prompted to enter a file to save the key in:

	~/.ssh/"<NAME_OF_SSH_KEY>"

DO NOT enter a passphrase. Passphrase-protected keys will not work with AWS

This will also create a public key file:

	~/.ssh/"<NAME_OF_SSH_KEY>".pub

You must upload the ssh public key to all regions (remove from the list any regions that already
have the ssh key). You can automate that process with a script like this one:

    for a in us-east-1 us-east-2 us-west-1 us-west-2 ap-south-1 ap-northeast-1 ap-southeast-1 ap-southeast-2 ap-northeast-2 eu-central-1 eu-west-1 eu-west-2 ; do aws ec2 import-key-pair --key-name NAME_OF_SSH_KEY --public-key-material file://~/.ssh/NAME_OF_SSH_KEY.pub --region $a ; done

To view the list of all ssh key pairs in all regions, you can run this script:

    for a in us-east-1 us-east-2 us-west-1 us-west-2 ap-south-1 ap-northeast-2 ap-southeast-1 ap-southeast-2 ap-northeast-1 eu-central-1 eu-west-1 eu-west-2 ; do echo $a ; aws ec2 describe-key-pairs --region $a ; done

To ensure that your SSH agent has key access, execute:

    ssh-add /path/to/keyfile

(Example: `ssh-add ~/.ssh/my_ssh_key`)

# Repos

## Required:

Check out the required repos into an easily accessible location.

DSI:

	git clone git@github.com:10gen/dsi.git

## Optional:

Mongo:

    git clone git@github.com:mongodb/mongo.git

Various benchmark clients supported by DSI:

    git clone git@github.com:mongodb-labs/YCSB.git
    git clone git@github.com:mongodb-labs/py-tpcc.git
    git clone git@github.com:mongodb-labs/benchmarks.git # sysbench benchmarks
    git clone git@github.com:mongodb/genny.git

Note: If you check out benchmark clients to your workstation, you can tell DSI their path in your
bootstrap.yml file:

    overrides:
      workload_setup:
        local_repos:
          ycsb: ...
          tpcc: ...
          benchmarks: ...
          genny: ...


## Dependencies

### Terraform

DSI uses Terraform. To save time, you can install it in your path.

* [Linux](https://releases.hashicorp.com/terraform/0.12.16/terraform_0.12.16_linux_amd64.zip)
* [Mac OS X](https://releases.hashicorp.com/terraform/0.12.16/terraform_0.12.16_darwin_amd64.zip)
* [Other binaries and checksums](https://releases.hashicorp.com/terraform/0.10.4/)

You must have version 0.12.16, despite newer versions possibly available.

Hint:

    terraform version

### Python PIP dependencies

If desired, create and activate a virtualenv to store required dependencies:

    virtualenv venv; source venv/bin/activate

To install necessary dependencies, run: 

    pip install --user -r PATH_TO_DSI/requirements.txt 

When finished using DSI, to escape the virtualenv, run: 

    deactivate

## Set Up Work Directory

To set up a work directory:

    DSI=./dsi
    WORK=any-path
    $EDITOR $DSI/configurations/bootstrap/bootstrap.example.yml
    $DSI/bin/bootstrap.py --directory $WORK --bootstrap-file configurations/bootstrap/bootstrap.example.yml
    cd $WORK

WORK can be an arbitrary directory path of your choosing. It will be created by bootstrap.py if it
doesn’t already exist and the environment will be set up within it. If --directory is not used, the
environment will be set up within the current working directory.

At this point you have a functioning DSI working directory and can provision a cluster. From this
point forward, we assume you are in the working directory.

## Provision Infrastructure

NOTE: You are provisioning resources in AWS. You need to clean them up later. See below for how to do that.

To provision some servers, execute:

    infrastructure_provisioning.py

This will allocate your requested cluster and also apply some common operating system configuration, such
as mount and format disks and configure ulimits. The input configuration for this step is in the file
`infrastructure_provisioning.yml`. Information about the infrastructure that gets provisioned is
located in `infrastructure_provisioning.out.yml`.

## Install workload specific dependencies

To setup the workloads, execute:

	workload_setup.py

This will setup the hosts for various kinds of workload types specified in workload_setup.yml. Note
that the setup is only done for matching types specified in test.run.type in test_control.py. This
step only has to be run once, even if you re-deploy the mongodb cluster and rerun tests.

Note that the benchmark client repositories are uploaded to the workload client host at this step.
This is significant if you edit your benchmark client files later.

## Deploy a Mongodb Cluster

In the working directory, execute:

    mongodb_setup.py

This will start a MongoDB cluster as specified in mongodb_setup.yml. It will download and install
the binary archive specified with `mongodb_binary_archive` key. 

To supply your own binary, such as from your Evergreen compile task, add its URL to
`mongodb_setup.yml`:

    mongodb_binary_archive: http://s3.amazonaws.com/mciuploads/dsi/<patch_info>.tar.gz

If you want to upload your own binary (such as via SCP), then you must set this option to the empty string: "". In that case this step will simply start mongodb using ~/mongodb/bin/mongod (or mongos)

## Run Tests

The tests to run are specified in `test_control.yml`. To run the tests, in the working directory, execute: 

    test_control.py

Running the tests will create a directory called `reports/` with the results from the run, mongod.log and diagnostic.data. 

## Connect to the Cluster

You can simply connect to all the machines using `conn.py` from the working directory. See `infrastructure_provisioning.out.yml` for a list of all the machines that have been allocated and their ip addresses. For instance, to connect to the workload client host:

    conn.py wc

Other targets you can connect to if desired: 

* wc: The client machine running the workload
* md.N: Server instance N (for mongod)
* ms.N: Server instance N (for mongos)
* cs.N: Server instance N (for config servers)

## Clean Up Your Resources

The simplest way is to execute:

    infrastructure_teardown.py

This will output a message confirming that your resources were destroyed:

    Destroy complete! Resources: 8 destroyed.

**Note:** The terraform state of your cluster is stored in your work directory. Don't delete the directory before you have successfully executed infrastructure_teardown.py

**Note:** You must run infrastructure_teardown.py in the work directory that you want to destroy resources for.  If you run the script in the wrong directory, it won't give an error but just say that "0 resources" were destroyed.

# See also

[Frequently Asked Questions](FAQ.md)
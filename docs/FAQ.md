# Frequently Asked Questions

## It takes hours to run all the tests in a task, how can I disable some tests?

Any tests, can be omitted by commenting or deleting them from test_control.yml. In particular, you
may want to start with deleting the tests called fio_, iperf_ and canary_.

By the way, you can do that for an evergreen patch build as well:

1. Checkout a branch of dsi repo, edit [your relevant test_control.yml file](https://github.com/henrikingo/dsi/tree/stable/configurations/test_control).
2. Submit your `evergreen patch -p sys-perf` job as usual.
3. In the dsi repo, submit your dsi changes:
   `evergreen set-module -m dsi -i <id from output of previous row>`
4. Start (aka finalize) your patch in Evergreen UI as usual. You should see the dsi changes as part of the diff.

At the end of each test, we run some validation checks (that we borrowed from the MongoDB
correctness jstests). This can be disabled in either of three different ways:

1. In `test_control.yml` set the `skip_validate` option to `true` for the test that you would like
   to disable the validation tests for. For an example, [see here](https://github.com/10gen/dsi/blob/5e742b8b26bd7d590c2f9ece0f4099ef128aa6a8/configurations/test_control/test_control.crud_workloads.yml#L43).
2. Remove the `validate:` section in your mongodb_setup.yml, [such as here](https://github.com/henrikingo/dsi/blob/1e679d9050985b5106b72af552c1a6d6853d89e1/configurations/mongodb_setup/mongodb_setup.replica.yml#L36-L39).
3. Making sure that the configuration `test_control.jstests_dir` is set to the empty string ""
   Either [here](https://github.com/10gen/dsi/blob/8efe9a3db74161ff132870227e4337de2a14d9af/configurations/defaults.yml#L145)
   or in your `test_control.yml` file, [such as here](https://github.com/10gen/dsi/blob/8efe9a3db74161ff132870227e4337de2a14d9af/configurations/test_control/test_control.initialsync-logkeeper.yml#L41).
4. Making sure your mongodb_binary_archive doesn't contain a `jstests/` directory.

## SSH_AUTH_SOCK error

If you see this error: ` Error connecting to SSH_AUTH_SOCK: dial unix /private/tmp/com.apple.launchd.PlFE7ecIaP/Listeners: connect: no such file or directory`

You need to have ssh-agent running: `ssh-agent bash` (or whatever shell you’re using) and `ssh-add ~/.ssh/"<NAME_OF_SSH_KEY>"`

## SSH key printed (--- BEGIN OPENSSH ...)

If you see an error on this step complaining about a parse error (you may see a dump of your key
file, looking something like "`--- BEGIN OPENSSH ...`"), that means your key file is in a format
that Terraform can't read. Here's a fix:

Navigate to the folder where you've stored your ssh keys (usually `~/.ssh`). Let's say you see the
files `my_key` and `my_key.pub` there. If you run `cat my_key`, you should see the contents of your
file, which is what Terraform dumped earlier.

Here, run the following command to convert your key files to a format Terraform understands (note
that you need to run this command once, on the my_key file only. The command will convert both
files):

    ssh-keygen -p -m PEM -f ~/.ssh/my_key

If you run `cat my_key` you should see that the file now starts with "`--- BEGIN RSA -`". Terraform
should now accept it.

## Errors in terraform.debug.log

When provisioning the EC2 instances (i.e infrastructure_provisioning.py), if you see below error to
iam/GetUser request in terraform.debug.log, then it's a harmless error.

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

# My cluster disappeared after 24 hours, but I need to run my benchmark for longer than that.

This question is specific to MongoDB internal systems:

In MongoDB AWS accounts, a reaper process deletes EC2 resources based on their `expire-on` tag.
By default when you use DSI, your cluster is set to expire after 24 hours. You can edit this in
your `overrides.yml`file:

    infrastructure_provisioning:
      tfvars:
        tags:
          expire-on-delta: 24


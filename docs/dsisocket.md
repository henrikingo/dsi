DSISOCKET
=========

The following configuration in test_control.yml will cause test_control.py to listen on the given
port on the workload_client host:

    dsisocket:
        enabled: true
        bind_addr: 127.0.0.1
        port: 27007

Your workload generator can connect to this port to issue commands while the test is running.
You can use all the same commands that are available in pre_task, pre_test, etc.

Command messages should however be serialized into json, not yaml. Note that quotation marks and
newlines need to be escaped with a backslash.

The implementation uses paramiko to open a reverse tunnel to the workload_client host. A single
daemon thread in test_control.py listens to, and executes, the commands. This means you can
only open a single connection to the port.

Examples
--------

    {"on_workload_client": {"exec": "echo \"HELLO THIS IS HENRIK CAN YOU HEAR ME?????!!!\"\necho \"(Yes, we can)\"\n"}}
    {"on_workload_client": {"exec": "pkill mongod"}}
    {"restart_mongodb": {"clean_logs": true, "clean_db_dir": false}}

Execute bash commands on workload_client. Successful example followed by a few failed executions.

    [ec2-user@ip-10-2-0-10 ~]$ sudo yum install telnet
    [ec2-user@ip-10-2-0-10 ~]$ telnet localhost 27007
    Trying 127.0.0.1...
    Connected to localhost.
    Escape character is '^]'.
    {"on_workload_client": {"exec": "echo \"HELLO THIS IS HENRIK CAN YOU HEAR ME?????!!!\"\necho \"(Yes, we can)\"\n"}}
    {"status_code": 0, "status": "OK", "message": "I think the command might have succeeded."}
    {"on_workload_client": {"foo": "echo \"HELLO THIS IS HENRIK CAN YOU HEAR ME?????!!!\"\necho \"(Yes, we can)\"\n"}}
    {"status_code": 2, "status": "EXECUTION_ERROR", "message": "Invalid command type"}
    {"on_workload_client": {1: "echo \"HELLO THIS IS HENRIK CAN YOU HEAR ME?????!!!\"\necho \"(Yes, we can)\"\n"}}
    {"status_code": 1, "status": "JSON_ERROR", "message": "Expecting property name enclosed in double quotes: line 1 column 25 (char 24)"}
    Connection closed by foreign host.
    [ec2-user@ip-10-2-0-10 ~]$ 

Restart entire MongoDB cluster(s).

    [ec2-user@ip-10-2-0-10 ~]$ telnet localhost 27007
    Trying 127.0.0.1...
    Connected to localhost.
    Escape character is '^]'.
    {"restart_mongodb": {"clean_logs": true, "clean_db_dir": false}}
    {"status_code": 0, "status": "OK", "message": "I think the command might have succeeded."}
    Connection closed by foreign host.
    [ec2-user@ip-10-2-0-10 ~]$ 

TODO
----

Currently DSI doesn't support executing a command on only a single host. This will be added in subsequent commits.
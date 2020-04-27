"""
Provide a network socket and api where workload clients can call DSI operations.

In particular, this allows to restart mongod processes during a test. But you can try
to use this for anything that can be called from pre_tast, pre_test, etc...

See docs/dsisocket.md for details.
"""
import json
import select
import threading

import structlog

from common.command_runner import run_pre_post_commands, EXCEPTION_BEHAVIOR

LOG = structlog.get_logger(__name__)


def start(host, config, current_test_id=None):
    """
    Start thread that will be accept()ing and handling incoming connections.

    :param Host host: A Host object, presumably holding a connection to the workload_client host.
    :param ConfigDict config: The DSI configuration dict.
    :param str current_test_id: test_id used as output or file prefix in some commands.
    """
    enabled = config['test_control']['dsisocket']['enabled']
    bind_addr = config['test_control']['dsisocket']['bind_addr']
    port = config['test_control']['dsisocket']['port']
    LOG.debug("dsisocket.start()", enabled=enabled, bind_addr=bind_addr, port=port)
    if enabled:
        LOG.info("Listening on dsisocket on workload_client", bind_addr=bind_addr, port=port)
        socket_ish = host.open_reverse_tunnel(bind_addr, port)
        LOG.debug("Opened reverse tunnel.", socket=socket_ish)
        thread = threading.Thread(target=handler, args=(socket_ish, config, current_test_id))
        thread.daemon = True
        thread.start()


def handler(socket, config, current_test_id):
    """
    Thread that will accept() on socket, then parse and execute commands received.

    Single thread, so only handles one incoming connection at a time. (per workload_client)
    :param paramiko.transport.Transport socket: A socket like object where we call accept()
    :param ConfigDict config: The DSI configuration.
    :param str current_test_id: test_id used as output or file prefix in some commands.
    """
    while True:
        channel = socket.accept(1000)
        if channel is None:
            continue
        while True:
            read, _, _ = select.select([channel], [], [])
            if channel in read:
                data = channel.recv(1024 * 10)
                if len(data) == 0:
                    break
                LOG.debug("dsisocket.handler() received data", data=data)
                command = None
                try:
                    # dsisocket commands should be json serialized
                    command = json.loads(data)
                except Exception as exc:  # pylint: disable=broad-except
                    LOG.error("Invalid dsisocket command: JSON parse error.", command=data)
                    LOG.error("Specific python error is:", exc_info=1)
                    send_return(channel, 'JSON_ERROR', str(exc))
                    continue

                try:
                    fake_command_list = [{"dsisocket": [command]}]
                    run_pre_post_commands("dsisocket", fake_command_list, config,
                                          EXCEPTION_BEHAVIOR.RERAISE, current_test_id)
                    send_return(channel, 'OK', "I think the command might have succeeded.")
                except Exception as exc:  # pylint: disable=broad-except
                    LOG.error("Invalid dsisocket command: execution error.", command=data)
                    LOG.error("Specific python error is:", exc_info=1)
                    send_return(channel, 'EXECUTION_ERROR', str(exc))
                    continue


def send_return(channel, status, msg=""):
    """
    Create a json object to hold return value of a command.

    :param channel: The socket to send the return message to.
    :param str status: One of 'OK', 'JSON_ERROR', 'EXECUTION_ERROR'.
    :param srt msg: Optional free form message.
    """
    status_code = {'OK': 0, 'JSON_ERROR': 1, 'EXECUTION_ERROR': 2}
    return_object = {'status_code': status_code[status], 'status': status, 'message': msg}
    return_json = json.dumps(return_object) + "\n"
    LOG.debug("dsisocket.handler() sending data", data=return_json)
    channel.send(return_json)

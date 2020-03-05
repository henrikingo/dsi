"""
Configure delays in networking between hosts, using tc.
"""
from collections import OrderedDict
from collections import namedtuple
from functools import partial
import structlog

import common.host_factory
import common.host_utils
from common.remote_host import RemoteHost
from common.thread_runner import run_threads

LOG = structlog.get_logger(__name__)


def establish_host_delays(target_host, command, config, prefix):
    """
    Configure network delays for outbound connections from target_host.

    Note: This method establishes delays on a single host using a single thread.

    :param RemoteHost target_host: An initialized RemoteHost object
    :param dict command: The configuration to apply. Give empty dict to reset delays to 0.
    :param ConfigDict config: The system configuration.
    :param str prefix: The id for the test related to the current command. If there
    is not a specific test related to the current command, the value of prefix should reflect the
    hook that the command belongs to, such as between_tests, post_task, and so on.
    """
    assert isinstance(target_host, RemoteHost), "host for network_delays must be a RemoteHost"
    _ = prefix
    LOG.debug("Establish network_delays.", host=target_host.hostname, alias=target_host.alias)
    delayed_host = DelayedHost(target_host, config, command)
    delayed_host.reset_delays()
    delayed_host.establish_delays()


def safe_reset_all_delays(config):
    """
    Wrap reset_all_delays in a try catch block.

    :param ConfigDict config: The global configuration.
    """
    try:
        reset_all_delays(config)
    except Exception as e:  # pylint: disable=broad-except
        LOG.error('Failed to reset network delays, but will continue.', err_msg=repr(e), exc_info=1)


def reset_all_delays(config):
    """
    Reset all network delays from all hosts in infrastructure_provisioning.out.

    Note: This method resets delays on all hosts using multiple threads in parallel.

    :param ConfigDict config: The global configuration.
    """
    LOG.info("Reset all network_delays.")
    hosts = common.host_utils.extract_hosts('all_hosts', config)
    LOG.debug("reset all network_delays.", hosts=hosts)
    run_threads([partial(reset_one_host, host_info, config) for host_info in hosts])


def reset_one_host(host_info, config):
    """
    Reset network delays on one host.
    """
    target_host = common.host_factory.make_host(host_info)
    assert isinstance(target_host, RemoteHost), "host for network_delays must be a RemoteHost"
    delayed_host = DelayedHost(target_host, config)
    delayed_host.reset_delays()


Command = namedtuple('Command', ['command', 'error'])


class DelayedHost(object):
    """ Class representing delays present at a given host. """
    def __init__(self, this_host, config, command=None):
        """
        :param Host this_host: a Host object to execute commands (e.g. via SSH).
        :param ConfigDict config: The entire DSI configuration.
        :param dict command: A DSI pre_task command, in particular the "network_delays" command.
                             None or empty dict will unset all delays to zero.
        """
        self.host = this_host
        self.config = config
        self.linux_distro = config["infrastructure_provisioning"]["tfvars"]["image"]
        sys_configs = config["infrastructure_provisioning"]["network_delays"]["sys_configs"]
        self.sys_config = sys_configs[self.linux_distro]
        self.interface = config["infrastructure_provisioning"]["network_delays"]["interface"]

        self.graph = DelayGraph(this_host.hostname, config, command)

    def reset_delays(self):
        """
        Set all delays to zero.
        """
        LOG.debug("reset delays", hostname=self.host.hostname, alias=self.host.alias)
        # This commonly fails if no delays were previously set, so suppress errors
        filter_str = "RTNETLINK answers: No such file or directory"
        # Deleting the root qdisc will fail if it doesn't exist; that's okay.
        del_qdisc_command = [
            "bash", "-c", "'sudo tc qdisc del dev " + self.interface + " root'" + " 2>&1 | " +
            "grep -v '" + filter_str + "'"
        ]
        return self.host.run(del_qdisc_command, quiet=True)

    def generate_delay_commands(self):
        """
        Generates all the tc commands needed to establish the delays.
        :return: a list of commands, where each Command is a tuple of command string,
        and the exception to throw if it does.
        """
        commands = []
        # If all delays are zero, do nothing
        if all([t["delay_ms"] == 0 and t["jitter_ms"] == 0 for t in self.graph.delays.values()]):
            return commands

        # Add the root qdisc
        commands.append(_generate_root_qdisc_command(self.interface))
        commands.append(_generate_class_command(1, self.sys_config["rate"], self.interface))
        # We start at classid 2 because the root qdisc takes classid 0 and default gets 1.
        classid = 2
        for ip_address in self.graph.delays:
            commands.append(
                _generate_class_command(classid, self.sys_config["rate"], self.interface))
            commands.append(
                _generate_delay_command(classid, ip_address, self.interface, self.graph.delays))
            commands.append(_generate_filter_command(classid, ip_address, self.interface))
            classid += 1

        return commands

    def establish_delays(self):
        """
        Establishes all described delays on the connected host. Raises an exception if
        commands fail that shouldn't.
        """
        for command in self.generate_delay_commands():
            if not self.host.run(command.command):
                raise command.error


# For more details on how linux traffic control works, check out:
# http://man7.org/linux/man-pages/man8/tc.8.html


def _generate_root_qdisc_command(interface):
    add_root_qdisc_command = [
        "bash", "-c", ("'sudo tc qdisc add dev " + interface + " root handle 1: "
                       "htb default 1'")
    ]
    return Command(
        add_root_qdisc_command,
        DelayError("Failed to add root qdisc. Command: {command}", add_root_qdisc_command[2]))


def _generate_class_command(classid, rate, interface):
    command_str = ("'sudo tc class add dev {interface} parent 1: classid 1:{classid} "
                   "htb rate {rate} prio 0'").format(interface=interface,
                                                     classid=str(classid),
                                                     rate=rate)
    command = ["bash", "-c", command_str]
    return Command(command, DelayError("Execution of tc command {command} failed.", command))


def _generate_delay_command(classid, remote_host, interface, delays):
    command_str = ("'sudo tc qdisc add dev {interface} parent 1:{classid} netem delay {delay_ms}ms "
                   "{jitter_ms}ms'").format(interface=interface,
                                            classid=classid,
                                            delay_ms=str(delays[remote_host]["delay_ms"]),
                                            jitter_ms=str(delays[remote_host]["jitter_ms"]))
    command = ["bash", "-c", command_str]
    return Command(command, DelayError("Execution of tc command {command} failed.", command))


def _generate_filter_command(classid, remote_host, interface):
    command_str = ("'sudo tc filter add dev {interface} protocol ip parent 1:0 prio 1 "
                   "u32 match ip dst {remote_host} flowid 1:{classid}'").format(
                       interface=interface, remote_host=remote_host, classid=classid)
    command = ["bash", "-c", command_str]
    return Command(command, DelayError("Execution of tc command {command} failed.", command))


class DelayGraph(object):
    """
    Class representing a graph of outbound delays.

    Note that this is called multi-threaded for a given target_host, so we build a graph here for
    the outbound connections for that host.
    """
    def __init__(self, my_public_ip, config, command=None):
        """
        Builds outbound graph to other hosts with tc config for each connection.

        :param str my_public_ip: public_ip of the host this is executing on (connection source).
        :param dict command: The object with delay configuration.
        :param ConfigDict config: The global config object.
        """
        self.my_public_ip = my_public_ip
        self.my_private_ip = None

        self.delays = OrderedDict()  # OrderedDict makes unit testing easier
        self.command = command if command is not None else {}
        self.config = config

        self._initialize_graph()
        self._group_delays()
        LOG.debug("Generated network_delays graph.",
                  my_public_ip=my_public_ip,
                  my_private_ip=self.my_private_ip,
                  delays=self.delays)

    def _initialize_graph(self):
        """
        Initialize a graph with hosts from infrastructure_provisioning.out paired, using defaults.
        """
        LOG.debug("Initialize delay graph.", command=self.command)
        network_delays = self.command.get("network_delays", {})
        default_delay = network_delays.get("delay_ms", 0)
        default_jitter = network_delays.get("jitter_ms", 0)
        for remote_host in self._get_destination_hosts():
            self.delays[remote_host] = {"delay_ms": default_delay, "jitter_ms": default_jitter}

    def _group_delays(self):
        """
        Override delays for those groups that were configured explicitly.
        """
        my_ip = self.my_private_ip if self.my_private_ip is not None else self.my_public_ip
        default_delay = self.command.get("delay_ms", 0)
        default_jitter = self.command.get("delay_ms", 0)
        groups = self.command.get("network_delays", {}).get("groups", [])
        LOG.debug("process groups in command", groups=groups)
        for group in groups:
            LOG.debug("next network delays group", group=group, my_ip=my_ip)
            if my_ip in group["hosts"]:
                for remote_host in group["hosts"]:
                    LOG.debug("Found remote_host in group", my_ip=my_ip, remote_host=remote_host)
                    if remote_host != my_ip:
                        LOG.debug("Set pairwise delay",
                                  my_ip=my_ip,
                                  remote_host=remote_host,
                                  delay_ms=group.get("delay_ms", default_delay),
                                  jitter_ms=group.get("jitter_ms", default_jitter))
                        self.delays[remote_host]["delay_ms"] = group.get("delay_ms", default_delay)
                        self.delays[remote_host]["jitter_ms"] = group.get(
                            "jitter_ms", default_jitter)

    def _get_destination_hosts(self):
        """
        Iterate over all (private) ips in infrastructure_provisioning.out, excluding myself.
        """
        ip_out = self.config["infrastructure_provisioning"].get("out", {})
        for _, sub_list in ip_out.items():
            assert isinstance(sub_list, list)
            for host_dict in sub_list:
                if host_dict["public_ip"] == self.my_public_ip:
                    self.my_private_ip = host_dict.get("private_ip")
                elif "private_ip" in host_dict:
                    yield host_dict["private_ip"]
                else:
                    yield host_dict["public_ip"]


class DelayError(Exception):
    """
    Class representing an error in establishing delays.
    """
    def __init__(self, msg, command=""):
        """
        :param msg: The message associated with this error. Include `{command}` in the string
        if a command is also passed in.
        :param command: The tc command responsible for this error.
        """
        super(DelayError,
              self).__init__(msg if command == "" else msg.format(command=" ".join(command)))

        self.command = command

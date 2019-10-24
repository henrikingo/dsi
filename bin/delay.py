"""
Classes that represent and allow establishment of
delays between hosts.
"""

from collections import OrderedDict
from collections import namedtuple

Command = namedtuple('Command', 'command allow_fail error')

# Network interface on which the delay should be established.
INTERFACE = "eth0"
EXPECTED_KERNEL = "4.15.0-1044-aws"

# We define htb qdiscs to have an absurdly high rate limit that is never hit.
RATE = "100tbit"


class DelaySpec(object):
    """ Class representing a single delay edge specification. """
    def __init__(self, delayspec_config):
        self.delay_ms = delayspec_config['delay_ms']
        self.jitter_ms = delayspec_config['jitter_ms']


class DelayNode(object):
    """ Class representing delays present at a given node. """
    def __init__(self):
        """
        :param host: a Host object connecting this node to the host it represents.
        """
        self.delays = OrderedDict()  # OrderedDict makes unit testing easier

    def add(self, ip_address, delay_spec):
        """
        Adds a planned delay to this node.
        :param ip_address: string IP address to which traffic will be delayed
        :param delay_ms: integer of the delay in milliseconds
        :param jitter_ms: integer of the jitter in milliseconds
        """

        if delay_spec.delay_ms < 0 or delay_spec.jitter_ms < 0:
            raise DelayError(
                ("Addition of delay failed: invalid delay or jitter. Given "
                 "delay: {delay}. Given jitter: {jitter}").format(delay=str(delay_spec.delay_ms),
                                                                  jitter=str(delay_spec.jitter_ms)))
        if ip_address in self.delays:
            raise DelayError(
                "Addition of delay failed: IP address already exists. Address: {ip_address}".format(
                    ip_address=ip_address))

        self.delays[ip_address] = delay_spec

    def generate_commands(self):
        """
        Generates all the tc commands needed to establish the delays.
        :return: a list of Commands, where each Command is a tuple of command string,
        whether that command is allowed to fail, and the exception to throw if it does.
        """
        commands = CommandList()

        # We assert the kernel version to protect against changes in how tc works
        _generate_kernel_assert(commands)

        # Deleting the root qdisc will fail if it doesn't exist; that's okay.
        del_qdisc_command = "sudo tc qdisc del dev " + INTERFACE + " root"
        commands.append(del_qdisc_command, None, True)

        if all([t.delay_ms == 0 and t.jitter_ms == 0 for t in self.delays.values()]):
            return commands.get_list()

        # Add the root qdisc
        add_root_qdisc_command = ("sudo tc qdisc add dev " + INTERFACE + " root handle 1: "
                                  "htb default 1")
        commands.append(
            add_root_qdisc_command,
            DelayError("Failed to add root qdisc. Command: " + add_root_qdisc_command,
                       add_root_qdisc_command))

        _generate_class_command(commands, 1)

        # We start at classid 2 because the root qdisc takes classid 0 and default gets 1.
        classid = 2
        for ip_address in self.delays:
            _generate_class_command(commands, classid)
            _generate_delay_command(commands, classid, ip_address, self.delays)
            _generate_filter_command(commands, classid, ip_address)
            classid += 1

        return commands.get_list()

    def establish_delays(self, host):
        """
        Establishes all described delays on the connected host. Raises an exception if
        commands fail that shouldn't.
        """
        for command in self.generate_commands():
            if not host.run(command.command) and not command.allow_fail:
                raise command.error


# For more details on how linux traffic control works, check out:
# http://man7.org/linux/man-pages/man8/tc.8.html


def _generate_class_command(commands, classid):
    command = ("sudo tc class add dev {interface} parent 1: classid 1:{classid} "
               "htb rate {rate} prio 0").format(interface=INTERFACE,
                                                classid=str(classid),
                                                rate=RATE)
    commands.append(command, DelayError("Execution of tc command {command} failed.", command))


def _generate_delay_command(commands, classid, ip_address, delays):
    command = ("sudo tc qdisc add dev {interface} parent 1:{classid} netem delay {delay_ms}ms "
               "{jitter_ms}ms").format(interface=INTERFACE,
                                       classid=classid,
                                       delay_ms=str(delays[ip_address].delay_ms),
                                       jitter_ms=str(delays[ip_address].jitter_ms))
    commands.append(command, DelayError("Execution of tc command {command} failed.", command))


def _generate_filter_command(commands, classid, ip_address):
    command = ("sudo tc filter add dev {interface} protocol ip parent 1:0 prio 1 "
               "u32 match ip dst {ip_address} flowid 1:{classid}").format(interface=INTERFACE,
                                                                          ip_address=ip_address,
                                                                          classid=classid)
    commands.append(command, DelayError("Execution of tc command {command} failed.", command))


def _generate_kernel_assert(commands):
    kernel_assert_command = "uname -r | cut -d '.' -f 1 | grep -q '{major}'" \
        .format(major=EXPECTED_KERNEL.split(".")[0])
    kernel_assert_error = DelayError(
        ("Trying to use `tc` to simulate network delays, "
         "but found an unexpected kernel version. Expected version {kernel}. "
         "This means the system image was recently upgraded. Please manually "
         "update `expected_kernel_version` in "
         "DSI and manually verify that `tc` is still setting the delays correctly. ").format(
             kernel=EXPECTED_KERNEL))
    commands.append(kernel_assert_command, kernel_assert_error)


class CommandList(object):
    """ Mini class making it easier to manage command lists."""
    def __init__(self):
        self.commands = []

    def append(self, command, error=None, allow_fail=False):
        """
        Creates a Command object and appends it to the list of commands.
        :param command: A string representing the command.
        :param error: The exception that is thrown if the command fails.
        :param allow_fail: Whether the command is allowed to fail without erroring.
        """
        self.commands.append(Command(command=command, error=error, allow_fail=allow_fail))

    def get_list(self):
        """
        :return: The list of commands that was built.
        """
        return self.commands


class DelayGraph(object):
    """
    Class representing a graph of delays.
    """
    def __init__(self, topology, delay_config):
        """
        Extracts configuration information from the topology and delay_config dicts.
        :param topology: The topology ConfigDict for a single cluster.
        :param delay_config: The delay ConfigDict for a single cluster.
        """
        self.graph = {}

        self._initialize_graph(topology, False)
        self._extract_delay_config(delay_config)
        self._set_default_delays()

    @staticmethod
    def from_topologies(topologies, delay_configs):
        """
        Creates a DelayGraph for each topology.
        :param topologies: a list of topology ConfigDicts, which is the same
        length as 'delay_configs'
        :param delay_configs: a list of delay ConfigDicts, which is the same
        length as 'topologies'
        :return: a list of DelayGraph instances
        """
        return [DelayGraph(topologies[i], delay_configs[i]) for i in range(len(topologies))]

    def get_node(self, ip_address):
        """
        Gets the DelayNode object corresponding to a given IP address.
        :param ip_address: the private IP address of the desired node.
        :return: the DelayNode object, with all delays added.
        """

        try:
            return self.graph[ip_address]
        except KeyError:
            raise DelayError("Tried to retrieve node for {ip_address}, but that IP address has "
                             "no delay specification.")

    def _initialize_graph(self, topology, is_standalone_list):
        """
        Reads the topology of a cluster and initializes the delay graph
        based on what nodes are present.
        :param topology: The topology ConfigDict for this cluster.
        :param is_standalone_list: Whether this 'topology' is just a
        list of standalone mongod configurations.
        """
        if is_standalone_list:
            for node in topology:
                private_ip = node['private_ip']
                self.graph[private_ip] = DelayNode()
            return

        if topology['cluster_type'] == 'sharded_cluster':
            self._initialize_graph(topology['configsvr'], True)
            self._initialize_graph(topology['mongos'], True)
            for replset in topology['shard']:
                self._initialize_graph(replset, False)
        elif topology['cluster_type'] == 'replset':
            self._initialize_graph(topology['mongod'], True)
        elif topology['cluster_type'] == 'standalone':
            private_ip = topology['private_ip']
            self.graph[private_ip] = DelayNode()

    def _extract_delay_config(self, delay_config):
        """
        Performs all actions needed to extract information from the delay ConfigDict.
        :param delay_config: A ConfigDict for a single cluster's delays.
        """
        self.default_delay = DelaySpec(delay_config['default'])

    def _set_default_delays(self):
        """
        Sets the default delays for all nodes in the graph.
        """
        for ip_1 in self.graph:
            for ip_2 in self.graph:
                if ip_1 != ip_2:
                    self.graph[ip_1].add(ip_2, self.default_delay)


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
        super(DelayError, self).__init__(msg if command == "" else msg.format(command=command))

        self.command = command

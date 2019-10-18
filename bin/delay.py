"""
Classes that represent and allow establishment of
delays between hosts.
"""


class DelaySpec(object):
    """ Class representing a single delay edge specification. """
    def __init__(self, delayspec_config):
        self.delay_ms = delayspec_config['delay_ms']
        self.jitter_ms = delayspec_config['jitter_ms']


class DelayNode(object):
    """ Class representing delays present at a given node. """
    def __init__(self):
        pass

    def add(self, ip_address, delay_spec):
        """
        Adds a planned delay to this node.
        :param ip_address: string IP address to which traffic will be delayed
        :param delay_ms: integer of the delay in ms
        :param jitter_ms: integer of the jitter in milliseconds
        """
        pass

    def establish_delays(self, host):
        """
        Establishes all described delays on the connected host. Raises an exception if
        commands fail that shouldn't.
        """
        pass


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

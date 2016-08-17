
"""
Paser output from terraform and generate necessary cluster definition files to track public and
private IP addresses. This file will generate the original ips.sh as well and YML file
"""

from __future__ import print_function
import logging
import sys
import yaml

LOG = logging.getLogger(__name__)


class TerraformOutputParser(object):  # pylint: disable=too-few-public-methods
    """
    DSI Terraform output, this class take input from stdin or file, parses it and generate
    YML and ips.sh files.
    """
    INSTANCE_TYPES = ["private_config_ip",
                      "private_member_ip",
                      "private_mongos_ip",
                      "public_config_ip",
                      "public_ip_mc",
                      "public_member_ip",
                      "public_mongos_ip"]

    INSTANCE_CATEGORY = {
        "private_config_ip": "configsvr",
        "private_member_ip": "mongod",
        "private_mongos_ip": "mongod",
        "public_config_ip": "configsvr",
        "public_ip_mc": "workload_client",
        "public_member_ip": "mongod",
        "public_mongos_ip": "mongos"
        }

    IP_SUBNET = {
        "private_config_ip": "private",
        "private_member_ip": "private",
        "private_mongos_ip": "private",
        "public_config_ip": "public",
        "public_ip_mc": "public",
        "public_member_ip": "public",
        "public_mongos_ip": "public"
        }

    def __init__(self, input_file=None):
        self._file = input_file
        # Dict to hold IP addresses.
        self._ips = {}
        self._parse_terraform_output()

    def _generate_yml(self):
        """To generate a string to represent output for infrastructure_provisioning.out.yml."""
        yml_data = {}
        yml_data["out"] = {}

        # mongod IP addresses
        if len(self._ips["public_member_ip"]) == 0 or len(self._ips["private_member_ip"]) == 0:
            LOG.error("Must have at least one mongod instance in the cluster!")
            raise ValueError("Must have at least one mongod instance in the cluster!")

        yml_data["out"]["mongod"] = []

        if len(self._ips["public_member_ip"]) != len(self._ips["private_member_ip"]):
            LOG.error("Mongod: public and private IP address counts mismatch!")
            raise ValueError("Mongod: public and private IP address counts mismatch!")

        for index in range(len(self._ips["private_member_ip"])):
            yml_data["out"]["mongod"].append({"public_ip": self._ips["public_member_ip"][index],
                                              "private_ip": self._ips["private_member_ip"][index]})

        # workload_client IP addresses
        if len(self._ips["public_ip_mc"]) == 0:
            LOG.error("Workload client: public and private IP address counts mismatch!")
            raise ValueError("Workload client: public and private IP address counts mismatch!")

        yml_data["out"]["workload_client"] = []

        for index in range(len(self._ips["public_ip_mc"])):
            yml_data["out"]["workload_client"].append(
                {"public_ip": self._ips["public_ip_mc"][index]})

        # mongos IP addresses
        if "public_mongos_ip" in self._ips:
            yml_data["out"]["mongos"] = []

            if len(self._ips["public_mongos_ip"]) != len(self._ips["private_mongos_ip"]):
                LOG.error("Mongos: public and private IP address counts mismatch!")
                raise ValueError('Mongos: public and private IP address counts mismatch!')

            for index in range(len(self._ips["private_mongos_ip"])):
                yml_data["out"]["mongos"].append(
                    {"public_ip": self._ips["public_mongos_ip"][index],
                     "private_ip": self._ips["private_mongos_ip"][index]})

        # configsvr IP addresses
        if "public_config_ip" in self._ips:
            yml_data["out"]["configsvr"] = []

            if len(self._ips["public_config_ip"]) != len(self._ips["private_config_ip"]):
                LOG.error("Configsvr: public and private IP address counts mismatch!")
                raise ValueError('Configsvr: public and private IP address counts mismatch!')

            for index in range(len(self._ips["private_config_ip"])):
                yml_data["out"]["configsvr"].append({
                    "public_ip": self._ips["public_config_ip"][index],
                    "private_ip": self._ips["private_config_ip"][index]
                    })

        return yaml.dump(yml_data, default_flow_style=False)

    def _parse_terraform_output(self):
        """To parse terraform output, and extract proper IP address"""

        if self._file is not None:
            LOG.info("Parse input file %s", self._file)
            fread = open(self._file, 'r')
        else:
            LOG.info("Parse from stadin")
            fread = sys.stdin

        # Read file and parse it.
        for line in fread:
            items = line.rstrip('\n').split(" ")
            if items[0] in self.INSTANCE_TYPES:
                instance_type = items[0]
                LOG.info("Found instance type %s", instance_type)
                self._ips[instance_type] = items[2:]

    def write_output_files(self):
        """
        Write details to infrastructure_provisioning.out.yml
        """
        with open("infrastructure_provisioning.out.yml", 'w') as fwrite:
            print(self._generate_yml(), file=fwrite)
            LOG.info("Generate YML file as:\n%s", self._generate_yml())

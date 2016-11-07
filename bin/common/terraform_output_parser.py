
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
                      "public_mongos_ip",
                      "public_mongod_ebs_ip",
                      "private_mongod_ebs_ip",
                      "public_mongod_seeded_ebs_ip",
                      "private_mongod_seeded_ebs_ip"]

    INSTANCE_CATEGORY = {
        "private_config_ip": "configsvr",
        "private_member_ip": "mongod",
        "private_mongos_ip": "mongod",
        "public_config_ip": "configsvr",
        "public_ip_mc": "workload_client",
        "public_mongod_ebs_ip": "mongod_ebs",
        "private_mongod_ebs_ip": "mongod_ebs",
        "public_mongod_seeded_ebs_ip": "mongod_seeded_ebs",
        "private_mongod_seeded_ebs_ip": "mongod_seeded_ebs",
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
        "public_mongod_ebs_ip": "public",
        "private_mongod_ebs_ip": "private",
        "public_mongod_seeded_ebs_ip": "public",
        "private_mongod_seeded_ebs_ip": "private",
        "public_mongos_ip": "public"
        }

    def __init__(self, input_file=None):
        self._file = input_file
        # Dict to hold IP addresses.
        self._ips = {}
        self._parse_terraform_output()

    def _get_ips(self, pub, priv, category, yml_data):
        if pub in self._ips:
            if len(self._ips[pub]) != len(self._ips[priv]):
                LOG.error(category + ": public and private IP address counts mismatch!")
                raise ValueError(category + ": public and private IP address counts mismatch!")

            if len(self._ips[pub]) > 0:
                yml_data["out"][category] = []
            else:
                # no ip address for this category, return the same back
                return yml_data

            for i in range(len(self._ips[priv])):
                yml_data["out"][category].append(
                    {"public_ip": self._ips[pub][i],
                     "private_ip": self._ips[priv][i]})

        return yml_data

    def _generate_yml(self):
        """To generate a string to represent output for infrastructure_provisioning.out.yml."""
        yml_data = {}
        yml_data["out"] = {}

        # mongod IP address
        yml_data = self._get_ips("public_member_ip", "private_member_ip",
                                 "mongod", yml_data)

        # mongod_ebs IP addresses
        yml_data = self._get_ips("public_mongod_ebs_ip", "private_mongod_ebs_ip",
                                 "mongod_ebs", yml_data)

        # mongod_seeded_ebs IP addresses
        yml_data = self._get_ips("public_mongod_seeded_ebs_ip", "private_mongod_seeded_ebs_ip",
                                 "mongod_seeded_ebs", yml_data)

        # workload_client IP addresses
        if len(self._ips["public_ip_mc"]) == 0:
            LOG.error("Workload client: public and private IP address counts mismatch!")
            raise ValueError("Workload client: public and private IP address counts mismatch!")

        yml_data["out"]["workload_client"] = []

        for index in range(len(self._ips["public_ip_mc"])):
            yml_data["out"]["workload_client"].append(
                {"public_ip": self._ips["public_ip_mc"][index]})

        # mongos IP addresses
        yml_data = self._get_ips("public_mongos_ip", "private_mongos_ip",
                                 "mongos", yml_data)

        # configsvr IP addresses
        yml_data = self._get_ips("public_config_ip", "private_config_ip",
                                 "configsvr", yml_data)

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

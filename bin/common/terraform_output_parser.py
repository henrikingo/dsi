"""
Paser output from terraform and generate necessary cluster definition files to track public and
private IP addresses. This file will generate the file "infrastructure_provisioning.out.yml"
"""

from __future__ import print_function
import logging
import sys

from common.config import ConfigDict

LOG = logging.getLogger(__name__)


class TerraformOutputParser(object):  # pylint: disable=too-few-public-methods
    """
    DSI Terraform output, this class takes input from stdin or file, parses it and generates
    YML infrastructure_provisioning.out.yml.
    """
    INSTANCE_TYPES = [
        "private_config_ip", "private_member_ip", "private_mongos_ip", "public_config_ip",
        "public_ip_mc", "public_member_ip", "public_mongos_ip"
    ]

    INSTANCE_CATEGORY = {
        "private_config_ip": "configsvr",
        "private_member_ip": "mongod",
        "private_mongos_ip": "mongos",
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

    def __init__(self, input_file=None, terraform_output=None):
        self._file = input_file
        self._terraform_output = terraform_output
        # Dict to hold IP addresses.
        self._ips = {}
        self.config_obj = ConfigDict("infrastructure_provisioning")
        self.config_obj.load()
        self._parse_terraform_output()

    def _get_ips(self, pub, priv, category, out_data):
        if pub in self._ips:
            if len(self._ips[pub]) != len(self._ips[priv]):
                LOG.error(category + ": public and private IP address counts mismatch!")
                raise ValueError(category + ": public and private IP address counts mismatch!")

            if self._ips[pub] and self._ips[pub][0]:
                # found category and IP address is not empty
                # IP address could be empty if category instance count is set to 0
                out_data[category] = []
                LOG.debug('_get_ips and non-empty pub in self._ips for category %s', category)
            else:
                # no ip address for this category, return the same back
                return out_data

            for i in range(len(self._ips[priv])):
                out_data[category].append({
                    "public_ip": self._ips[pub][i],
                    "private_ip": self._ips[priv][i]
                })

        return out_data

    def _generate_output(self):
        """Update the configuration object for output from infrastructure_provisioning stage."""
        out_data = {}
        # mongod IP address
        out_data = self._get_ips("public_member_ip", "private_member_ip", "mongod", out_data)

        # workload_client IP addresses
        if not self._ips["public_ip_mc"]:
            LOG.error("Workload client: public and private IP address counts mismatch!")
            raise ValueError("Workload client: public and private IP address counts mismatch!")

        out_data["workload_client"] = []

        for index in range(len(self._ips["public_ip_mc"])):
            out_data["workload_client"].append({"public_ip": self._ips["public_ip_mc"][index]})

        # mongos IP addresses
        out_data = self._get_ips("public_mongos_ip", "private_mongos_ip", "mongos", out_data)

        # configsvr IP addresses
        out_data = self._get_ips("public_config_ip", "private_config_ip", "configsvr", out_data)

        self.config_obj['infrastructure_provisioning']['out'] = out_data

    def _parse_terraform_output(self):
        """To parse terraform output, and extract proper IP address"""
        if self._terraform_output:
            LOG.info("Parse from string")
            fread = self._terraform_output.splitlines()
        elif self._file is not None:
            LOG.info("Parse input file %s", self._file)
            fread = open(self._file, 'r')
        else:
            LOG.info("Parse from stdin")
            fread = sys.stdin

        # Read file and parse it.
        for line in fread:
            items = line.rstrip('\n').split(" ")
            if items[0] in self.INSTANCE_TYPES:
                instance_type = items[0]
                LOG.info("Found instance type %s", instance_type)
                self._ips[instance_type] = [item for item in items[2:] if item != '']

    def write_output_files(self):
        """
        Write details to infrastructure_provisioning.out.yml
        """
        self._generate_output()
        self.config_obj.save()
        LOG.info("Generate infrastructure_provisioning.out.yml")

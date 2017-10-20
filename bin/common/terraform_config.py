# pylint: disable=attribute-defined-outside-init,too-many-instance-attributes,too-many-arguments
"""
This file take input and generate necessary configuration files for terraform configuration.
This function should be called from terraform cluster configuration folder.
"""

from __future__ import print_function
import json
import datetime
import logging
import socket
import requests
# RequestException is the parent exception for all requests.exceptions.*
# http://docs.python-requests.org/en/master/_modules/requests/exceptions/
from requests.exceptions import RequestException

from common.config import ConfigDict

LOG = logging.getLogger(__name__)

# Constant to define instance classes with placement group support
INSTANCE_CLASSES_SUPPORT_PLACEMENT_GROUP = ["c3", "c4", "m4", "r3", "d2", "i2", "hi1", "hs1"]


def assert_value(condition, message):
    """To raise ValueError if condition is false."""
    if not condition:
        LOG.error(message)
        raise ValueError(message)


def generate_expire_on_tag(now=None, day_delta=2):
    """
    This will generate expire-on tag based on current time or input time,
    expired-on tag will be (now + day_delta) day, default to 2 day.
    """
    if now is None:
        now = datetime.datetime.now()
    expire_on = now + datetime.timedelta(days=day_delta)
    return "{}-{}-{}".format(expire_on.year, expire_on.month, expire_on.day)


def support_placement_group(instance_type):
    """
    Test whether whether an instance type support placement group.
    Exampes:
        c3.8xlarge -> True
        m3.2xlarge -> False
    """

    return instance_type.split(".")[0] in INSTANCE_CLASSES_SUPPORT_PLACEMENT_GROUP


def generate_runner():
    """Get the IP address of the (evergreen) runner for labelling cluster

    Will try to get the public IP from AWS metadata first, then from
    reverse lookup, and then fall back to using the hostname

    """
    try:
        response = requests.get(
            'http://169.254.169.254/latest/meta-data/public-hostname', timeout=0.01)
        response.raise_for_status()
        return response.text
    except RequestException as exception:
        LOG.warning("Terraform_config.py generate_runner could not access AWS"
                    "meta-data. Falling back to other methods")
        LOG.warning(repr(exception))

    try:
        response = requests.get('http://ip.42.pl/raw', timeout=1)
        response.raise_for_status()
        return response.text
    except RequestException as exception:
        LOG.warning("Terraform_config.py generate_runner could not access ip.42.pl"
                    "to get public IP. Falling back to gethostname")
        LOG.warning(repr(exception))

    return socket.gethostname()


class TerraformConfiguration(object):
    """
    DSI Terraform configuration
    """

    # We limit mongod instance type based on the requirement to have at least
    # 2 SSD, and we need a known type so that we can carry out pre-qualification.
    MONGOD_INSTANCE_TYPE = [
        "c4.8xlarge", "c3.8xlarge", "c3.4xlarge", "c3.2xlarge", "c3.xlarge", "m3.2xlarge",
        "m3.xlarge", "g2.8xlarge", "r3.8xlarge", "d2.8xlarge", "d2.4xlarge", "d2.2xlarge",
        "d2.xlarge", "i2.8xlarge", "i2.4xlarge", "i2.2xlarge", "i2.xlarge"
    ]

    INSTANCE_ROLES = [
        "mongod", "mongos", "workload", "configsvr", "mongod_ebs", "mongod_seeded_ebs"
    ]

    MONGOD_ROLES = ["mongod", "mongod_ebs", "mongod_seeded_ebs"]

    def __init__(self,
                 topology=None,
                 region=None,
                 availability_zone=None,
                 now=None,
                 day_delta=2,
                 use_config=True):
        if topology is not None:
            self.topology = topology
        if region is not None:
            self.region = region
        if availability_zone is not None:
            self.availability_zone = availability_zone
        self.now = now
        self.define_day_delta(day_delta)
        self.runner = generate_runner()
        self.status = "running"
        # always update expire-on
        self.expire_on = generate_expire_on_tag(now, self.day_delta)
        if use_config:
            self._update_from_config()

    def define_instance(self, dsi_config, role, count, instance_type):
        """
        A function to dynamically define parameters for an instance type.
        This can be used to configure mongod/mongos/workload/configsvr.

        :param object dsi_config config object for DSI
        :param str role: role of the instance, must in predefined list
        :param int count: number of instances
        :param str instance_type: AWS instance type, must in predefined list
        """
        instance_type = instance_type.lower()

        assert_value(role in self.INSTANCE_ROLES, "Instance role must be in {}, got {} instead"
                     .format(str(self.INSTANCE_ROLES), role))

        if role in self.MONGOD_ROLES:
            # this is mongod type of instance, raise exception in case of wrong type
            assert_value(instance_type in self.MONGOD_INSTANCE_TYPE,
                         "Instance type must be in {}, got {} instead".format(
                             str(self.MONGOD_INSTANCE_TYPE), instance_type))

        if role == "workload":
            # must have at least one workload client
            assert_value(count > 0, "Must have at least one workload instance, got {} instead"
                         .format(count))

        setattr(self, role + "_instance_count", count)
        setattr(self, role + "_instance_type", instance_type)

        if support_placement_group(instance_type):
            setattr(self, role + "_instance_placement_group", 'yes')
        else:
            setattr(self, role + "_instance_placement_group", "no")  # default to no placement group

        if role == "mongod_ebs":
            # user must define ebs related details, such as:
            #       "mongod_ebs_size" : 200
            #       "mongod_ebs_iops" : 1500
            self.mongod_ebs_size = dsi_config["tfvars"]["mongod_ebs_size"]
            self.mongod_ebs_iops = dsi_config["tfvars"]["mongod_ebs_iops"]

        if role == "mongod_seeded_ebs":
            # user must define seeded ebs related details, such as:
            #       mongod_seeded_ebs_snapshot_id : "snap-bf69915c"
            #       mongod_seeded_ebs_iops        : 1500
            self.mongod_seeded_ebs_snapshot_id =\
                dsi_config["tfvars"]["mongod_seeded_ebs_snapshot_id"]
            self.mongod_seeded_ebs_iops = dsi_config["tfvars"]["mongod_seeded_ebs_iops"]

    def define_mongodb_url(self, url):
        """
        Define a url to download mongodb.tar.gz, may move this out of here in the future.
        """
        self.mongourl = url

    def define_day_delta(self, day_delta):
        """To define how many days in the future to adjust expire_on"""
        assert_value(day_delta > 0,
                     "expire_on must be tomorrow of beyond, received {}".format(day_delta))
        self.day_delta = day_delta
        self.expire_on = generate_expire_on_tag(self.now, self.day_delta)

    def _update_from_config(self):
        """Update terraform configuration based on provisioning file."""

        config_obj = ConfigDict("infrastructure_provisioning")
        config_obj.load()

        dsi_config = config_obj['infrastructure_provisioning']

        for role in self.INSTANCE_ROLES:
            # update instance definition if they present in the provisioning file
            if role + "_instance_count" in dsi_config["tfvars"].keys():
                assert_value(role + "_instance_type" in dsi_config["tfvars"].keys(),
                             "Should define both count and type for {}".format(role))

                # update both count and type
                self.define_instance(dsi_config, role, dsi_config["tfvars"][role
                                                                            + "_instance_count"],
                                     dsi_config["tfvars"][role + "_instance_type"])

        # update ssh key name (must match AWS' name)
        if "ssh_key_name" in dsi_config["tfvars"].keys():
            self.key_name = dsi_config["tfvars"]["ssh_key_name"]

        # update ssh key file location
        if "ssh_key_file" in dsi_config["tfvars"].keys():
            self.key_file = dsi_config["tfvars"]["ssh_key_file"]

        # update region file
        if "region" in dsi_config["tfvars"].keys():
            self.region = dsi_config["tfvars"]["region"]

        # update availability_zone file
        if "availability_zone" in dsi_config["tfvars"].keys():
            self.availability_zone = dsi_config["tfvars"]["availability_zone"]

        # update day delta value
        if "expire-on-delta" in dsi_config["tfvars"]["tags"].keys():
            self.define_day_delta(dsi_config["tfvars"]["tags"]["expire-on-delta"])

        # update owner tag
        if "owner" in dsi_config["tfvars"]["tags"].keys():
            self.owner = dsi_config["tfvars"]["tags"]["owner"]

        # update task id tag
        if "runtime" in config_obj.keys() and "task_id" in config_obj["runtime"].keys():
            self.task_id = config_obj["runtime"]["task_id"]
        else:
            LOG.info("Couldn't find runtime or task_id in config")

        # update cluster_name tag
        if "cluster_name" in dsi_config["tfvars"].keys():
            self.cluster_name = dsi_config["tfvars"]["cluster_name"]

    def to_json(self, compact=False, file_name=None):
        """To create JSON configuration string."""
        json_str = ""
        json_dict = self.__dict__.copy()

        # need remove some of the field, such as day_delta which is not used by Terraform
        json_dict.pop("day_delta", None)
        json_dict.pop("now", None)

        if compact:
            json_str = json.dumps(
                self, default=lambda o: json_dict, separators=(',', ':'), sort_keys=True)
        else:
            json_str = json.dumps(self, default=lambda o: json_dict, sort_keys=True, indent=4)

        LOG.info(json_str)
        if file_name is not None:
            # write to file as well
            with open(file_name, 'w') as fwrite:
                print(json_str, file=fwrite)
        return json_str

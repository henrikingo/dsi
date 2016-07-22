# pylint: disable=attribute-defined-outside-init,too-many-instance-attributes,too-many-arguments

"""
This file take input and generate necessary configuration files for terraform configuration.
This function should be called from terraform cluster configuration folder.
"""

from __future__ import print_function
import json
import datetime
import logging

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


class TerraformConfiguration(object):
    """
    DSI Terraform configuration
    """

    # We limit mongod instance type based on the requirement to have at least
    # 2 SSD, and we need a known type so that we can carry out pre-qualification.
    MONGOD_INSTANCE_TYPE = [
        "c3.8xlarge",
        "c3.4xlarge",
        "c3.2xlarge",
        "c3.xlarge",
        "m3.2xlarge",
        "m3.xlarge",
        "g2.8xlarge",
        "r3.8xlarge",
        "d2.8xlarge",
        "d2.4xlarge",
        "d2.2xlarge",
        "d2.xlarge",
        "i2.8xlarge",
        "i2.4xlarge",
        "i2.2xlarge",
        "i2.xlarge"
        ]

    INSTANCE_ROLES = ["mongod", "mongos", "workload", "configserver"]

    def __init__(self, topology=None, region=None, availability_zone=None, now=None, day_delta=2):
        if topology is not None:
            self.topology = topology
        if region is not None:
            self.region = region
        if availability_zone is not None:
            self.availability_zone = availability_zone

        # always update expire-on
        self.expire_on = generate_expire_on_tag(now, day_delta)

    def _define_instance(self, role, count, instance_type):
        """
        A private function to dynamically define parameters for an instance type.
        This can be used to configure mongod/mongos/workload/configserver.
        """
        instance_type = instance_type.lower()

        assert_value(role in self.INSTANCE_ROLES,
                     "Instance role must be in {}, got {} instead"
                     .format(str(self.INSTANCE_ROLES), role))

        setattr(self, role + "_instance_count", count)
        setattr(self, role + "_instance_type", instance_type)

        if support_placement_group(instance_type):
            setattr(self, role + "_instance_placement_group", 'yes')
        else:
            setattr(self, role + "_instance_placement_group", "no")  # default to no placement group

    def define_mongod_instance(self, count, instance_type):
        """To define mongod instances."""
        assert_value(isinstance(count, int) and count > 0, "Count for mongod instance must > 0")
        assert_value(instance_type in self.MONGOD_INSTANCE_TYPE,
                     "Monogd instance type must be in " + str(self.MONGOD_INSTANCE_TYPE) + " class")

        self._define_instance("mongod", count, instance_type)

    def define_mongos_instance(self, count, instance_type):
        """To define mongos instances."""
        assert_value(isinstance(count, int) and count >= 0, "Count for mongos instance must >= 0")

        self._define_instance("mongos", count, instance_type)

    def define_workload_instance(self, count, instance_type):
        """To define workload instances."""
        assert_value(isinstance(count, int) and count > 0, "Count for workload instance must > 0")
        assert_value(support_placement_group(instance_type),
                     "Workload generator must support placement group")

        self._define_instance("workload", count, instance_type)

    def define_configserver_instance(self, count, instance_type):
        """To define workload instances."""
        assert_value(isinstance(count, int) and count > 0,
                     "Count for configserver instance must > 0")

        self._define_instance("configserver", count, instance_type)

    def define_mongoodb_url(self, url):
        """
        Define a url to download mongodb.tar.gz, may move this out of here in the future.
        """
        self.mongourl = url

    def to_json(self, compact=False, file_name=None):
        """To create JSON configuration string."""
        json_str = ""
        if compact:
            json_str = json.dumps(self, default=lambda o: o.__dict__,
                                  separators=(',', ':'), sort_keys=True)
        else:
            json_str = json.dumps(self, default=lambda o: o.__dict__,
                                  sort_keys=True, indent=4)

        if file_name is not None:
            # write to file as well
            with open(file_name, 'w') as fwrite:
                print(json_str, file=fwrite)
        return json_str

#pylint: disable=attribute-defined-outside-init,too-many-instance-attributes,too-many-arguments

'''
This file take input and generate necessary configuration files for terraform configuration.
This function should be called from terraform cluster configuration folder.
'''

from __future__ import print_function
import json
import datetime
import logging

LOG = logging.getLogger(__name__)

def assert_value(condition, message):
    '''raise ValueError if condition is false'''
    if not condition:
        LOG.error(message)
        raise ValueError(message)

def generate_expire_on_tag(now=None, day_delta=1):
    '''
    this will generate expire-on tag based on current time or input time,
    expired-on tag will be (now + day_delta) day, default to 1 day
    '''
    if now is None:
        now = datetime.datetime.now()
    expire_on = now + datetime.timedelta(days=day_delta)
    return "{}-{}-{}".format(expire_on.year, expire_on.month, expire_on.day)

class TerraformConfiguration(object):
    """
    DSI Terraform configuration
    """

    # we limit mongod insance type since there are some requirement for it
    # such as must have 2 SSD, and we need known type so that we can carry
    # out pre-qualification
    MONGOD_INSTANCE_TYPE = ["c3.8xlarge", "c3.4xlarge", "c3.2xlarge"]

    def __init__(self, topology=None, region=None, availability_zone=None, now=None, day_delta=1):
        if topology is not None:
            self.topology = topology
        if region is not None:
            self.region = region
        if availability_zone is not None:
            self.availability_zone = availability_zone

        # always update expire-on
        self.expire_on = generate_expire_on_tag(now, day_delta)

    def define_mongod_instance(self, count, instance_type):
        """To define mongod instances"""

        assert_value(isinstance(count, int) and count > 0, "Count for mongod instance must > 0")
        assert_value(instance_type in self.MONGOD_INSTANCE_TYPE,
                     "monogd instance type must be in " + str(self.MONGOD_INSTANCE_TYPE))

        self.mongod_instance_count = count
        self.mongod_instance_type = instance_type

    def define_mongos_instance(self, count, instance_type):
        """To define mongod instances"""
        assert_value(isinstance(count, int) and count >= 0, "Count for mongos instance must >= 0")

        self.mongos_instance_count = count
        self.mongos_instance_type = instance_type

    def define_workload_instance(self, count, instance_type):
        """To define workload instances"""
        assert_value(isinstance(count, int) and count > 0, "Count for workload instance must > 0")

        self.workload_instance_count = count
        self.workload_instance_type = instance_type

    def define_mongoodb_url(self, url):
        '''
        define url to download mongodb.tar.gz, may move this out of here in the future
        '''
        self.mongourl = url

    def to_json(self, compact=False, file_name=None):
        '''to JSON configuration string'''
        json_str = ""
        if compact:
            json_str = json.dumps(self, default=lambda o: o.__dict__,
                                  separators=(',', ':'))
        else:
            json_str = json.dumps(self, default=lambda o: o.__dict__,
                                  sort_keys=True, indent=4)

        if file_name is not None:
            # write to file as well
            with open(file_name, 'w') as fwrite:
                print(json_str, file=fwrite)
        return json_str

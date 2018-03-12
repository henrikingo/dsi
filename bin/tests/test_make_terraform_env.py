"""test file for terraform_env"""

from __future__ import print_function
import datetime
import logging
import os
import unittest
from mock import patch

import requests
import requests.exceptions
from testfixtures import LogCapture

from common.config import ConfigDict
from common import terraform_config


class TestTerraformConfiguration(unittest.TestCase):
    """To test terraform configuration class."""

    def setUp(self):
        ''' Load self.config (ConfigDict) and set some other common values '''

        self.old_dir = os.getcwd()  # Save the old path to restore Note
        # that this chdir only works without breaking relative imports
        # because it's at the same directory depth
        os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../../docs/config-specs/')
        self.config = ConfigDict('infrastructure_provisioning')
        self.config.load()

        cookiejar = requests.cookies.RequestsCookieJar()
        request = requests.Request('GET', 'http://ip.42.pl/raw')
        request.prepare()
        self.response_state = {
            'cookies': cookiejar,
            '_content': 'ip.42.hostname',
            'encoding': 'UTF-8',
            'url': u'http://ip.42.pl/raw',
            'status_code': 200,
            'request': request,
            'elapsed': datetime.timedelta(0, 0, 615501),
            'headers': {
                'Content-Length': '14',
                'X-Powered-By': 'PHP/5.6.27',
                'Keep-Alive': 'timeout=5, max=100',
                'Server': 'Apache/2.4.23 (FreeBSD) OpenSSL/1.0.1l-freebsd PHP/5.6.27',
                'Connection': 'Keep-Alive',
                'Date': 'Tue, 25 Jul 2017 14:20:06 GMT',
                'Content-Type': 'text/html; charset=UTF-8'
            },
            'reason': 'OK',
            'history': []
        }

    def tearDown(self):
        """Restore working directory"""
        os.chdir(self.old_dir)

    @patch('socket.gethostname')
    @patch('requests.get')
    def test_generate_runner_timeout_hostname(self, mock_requests_get, mock_gethostname):
        """ Test generate runner and error cases. Fall back to gethostname """
        mock_requests_get.side_effect = requests.exceptions.Timeout()
        mock_requests_get.return_value = "MockedNotRaise"
        mock_gethostname.return_value = "HostName"
        with LogCapture(level=logging.INFO) as log_output:
            self.assertEqual(terraform_config.generate_runner(), "HostName")
            log_output.check(('common.terraform_config', 'INFO',
                              "Terraform_config.py generate_runner could not access AWS"
                              "meta-data. Falling back to other methods"),
                             ('common.terraform_config', 'INFO', 'Timeout()'),
                             ('common.terraform_config', 'INFO',
                              "Terraform_config.py generate_runner could not access ip.42.pl"
                              "to get public IP. Falling back to gethostname"),
                             ('common.terraform_config', 'INFO', 'Timeout()'))

    @patch('socket.gethostname')
    @patch('requests.get')
    def test_generate_runner_awsmeta(self, mock_requests_get, mock_gethostname):
        """ Test generate runner, successfully getting data from aws """
        request = requests.Request('GET', 'http://169.254.169.254/latest/meta-data/public-hostname')
        request.prepare()
        response = requests.models.Response()
        self.response_state['request'] = request
        self.response_state['_content'] = 'awsdata'
        response.__setstate__(self.response_state)
        mock_requests_get.return_value = response
        mock_gethostname.return_value = "HostName"
        with LogCapture(level=logging.INFO) as log_output:
            self.assertEqual(terraform_config.generate_runner(), "awsdata")
            log_output.check()

    @patch('socket.gethostname')
    @patch('requests.get')
    def test_generate_runner_timeout_ip42(self, mock_requests_get, mock_gethostname):
        """ Test generate runner and error cases. Fall back to ip.42 call """
        mock_gethostname.return_value = "HostName"
        response = requests.models.Response()
        response.__setstate__(self.response_state)
        mock_requests_get.side_effect = [requests.exceptions.Timeout(), response]
        with LogCapture(level=logging.INFO) as log_output:
            self.assertEqual(terraform_config.generate_runner(), 'ip.42.hostname')
            log_output.check(('common.terraform_config', 'INFO',
                              "Terraform_config.py generate_runner could not access AWS"
                              "meta-data. Falling back to other methods"),
                             ('common.terraform_config', 'INFO', 'Timeout()'))

    @patch('socket.gethostname')
    @patch('requests.get')
    def test_generate_runner_timeout_ip42_404(self, mock_requests_get, mock_gethostname):
        """ Test generate runner and error cases. Timeout on aws, and 404 on ip42 """
        mock_gethostname.return_value = "HostName"
        response = requests.models.Response()
        self.response_state['status_code'] = 404
        response.__setstate__(self.response_state)
        mock_requests_get.side_effect = [requests.exceptions.Timeout(), response]
        with LogCapture(level=logging.INFO) as log_output:
            self.assertEqual(terraform_config.generate_runner(), 'HostName')
            log_output.check(
                ('common.terraform_config', 'INFO',
                 "Terraform_config.py generate_runner could not access AWS"
                 "meta-data. Falling back to other methods"),
                ('common.terraform_config', 'INFO', 'Timeout()'),
                ('common.terraform_config', 'INFO',
                 'Terraform_config.py generate_runner could not access ip.42.plto get public IP.'
                 ' Falling back to gethostname'),
                ('common.terraform_config', 'INFO',
                 "HTTPError(u'404 Client Error: OK for url: http://ip.42.pl/raw',)"))

    @patch('socket.gethostname')
    @patch('requests.get')
    def test_generate_runner_404_and_timeout(self, mock_requests_get, mock_gethostname):
        """ Test generate runner and error cases. 404 on aws and timeout on ip42.
        Fall back to gethostname """
        request = requests.Request('GET', 'http://169.254.169.254/latest/meta-data/public-hostname')
        request.prepare()
        self.response_state['request'] = request
        self.response_state['status_code'] = 404
        self.response_state['url'] = 'http://169.254.169.254/latest/meta-data/public-hostname'
        response = requests.models.Response()
        response.__setstate__(self.response_state)
        mock_requests_get.side_effect = [response, requests.exceptions.Timeout()]
        mock_gethostname.return_value = "HostName"
        with LogCapture(level=logging.INFO) as log_output:
            self.assertEqual(terraform_config.generate_runner(), "HostName")
            log_output.check(
                ('common.terraform_config', 'INFO',
                 'Terraform_config.py generate_runner could not access AWSmeta-data.'
                 ' Falling back to other methods'),
                ('common.terraform_config', 'INFO', "HTTPError(u'404 Client Error: OK for url: "
                 "http://169.254.169.254/latest/meta-data/public-hostname',)"),
                ('common.terraform_config', 'INFO',
                 'Terraform_config.py generate_runner could not access ip.42.plto get public IP.'
                 ' Falling back to gethostname'), ('common.terraform_config', 'INFO', 'Timeout()'))

    @patch('socket.gethostname')
    @patch('requests.get')
    def test_retrieve_runner_instance_id_awsmeta(self, mock_requests_get, mock_gethostname):
        """ Test retrieve runner instance id, successfully getting data from aws """
        request = requests.Request('GET', 'http://169.254.169.254/latest/meta-data/instance-id')
        request.prepare()
        response = requests.models.Response()
        self.response_state['request'] = request
        self.response_state['_content'] = 'awsdata'
        response.__setstate__(self.response_state)
        mock_requests_get.return_value = response
        mock_gethostname.return_value = "HostName"
        with LogCapture(level=logging.INFO) as log_output:
            self.assertEqual(terraform_config.generate_runner(), "awsdata")
            log_output.check()

    @patch('socket.gethostname')
    @patch('requests.get')
    def test_retrieve_runner_instance_id_timeout(self, mock_requests_get, mock_gethostname):
        """ Test retrieve runner instance id error case."""
        mock_gethostname.return_value = "HostName"
        response = requests.models.Response()
        response.__setstate__(self.response_state)
        mock_requests_get.side_effect = [requests.exceptions.Timeout(), response]
        with LogCapture(level=logging.INFO) as log_output:
            self.assertEqual(terraform_config.retrieve_runner_instance_id(),
                             "deploying host is not an EC2 instance")
            log_output.check(('common.terraform_config', 'INFO',
                              "Terraform_config.py retrieve_runner_instance_id could not access AWS"
                              "instance id."), ('common.terraform_config', 'INFO', 'Timeout()'))

    @patch('common.terraform_config.uuid4')
    @patch('common.terraform_config.generate_runner')
    @patch('common.terraform_config.retrieve_runner_instance_id')
    # pylint: disable=invalid-name
    def test_default(self, mock_retrieve_runner_instance_id, mock_generate_runner, mock_uuid4):
        """Test default terraform configuration."""
        #pylint: disable=line-too-long
        mock_uuid4.return_value = "mock-uuid-1234"
        mock_retrieve_runner_instance_id.return_value = 'i-0c2aad81dfac5ca6e'
        mock_generate_runner.return_value = '111.111.111.111'
        # Can't mock builtin things like datetime.now
        expected_date = datetime.date.today() + datetime.timedelta(1)
        expected_date_string = "{}-{}-{}".format(expected_date.year, expected_date.month,
                                                 expected_date.day)

        expected_string = '{"Project":"sys-perf","Variant":"Linux 3-shard cluster","availability_zone":"us-west-2a","cluster_name":"shard","configsvr_instance_count":3,"configsvr_instance_type":"t1.micro","expire_on":"' + expected_date_string + '","mongod_instance_count":9,"mongod_instance_type":"c3.8xlarge","mongod_placement_group":"shard-mock-uuid-1234","mongos_instance_count":3,"mongos_instance_type":"c3.8xlarge","mongos_placement_group":"shard-mock-uuid-1234","owner":"linus.torvalds@10gen.com","placement_group":"shard-mock-uuid-1234","region":"us-west-2","runner":"111.111.111.111","ssh_key_file":"~/.ssh/linustorvalds.pem","ssh_key_name":"linus.torvalds","ssh_user":"ec2-user","status":"running","task_id":"123...","workload_instance_count":1,"workload_instance_type":"c3.8xlarge","workload_placement_group":"shard-mock-uuid-1234"}'
        tf_config = terraform_config.TerraformConfiguration(self.config)
        json_string = tf_config.to_json(compact=True)

        self.assertEqual(json_string, expected_string)

    def test_generate_expire_on_tag(self):
        """Test expire-on tag generator."""
        # Can't mock builtin things like datetime.now
        expected_date = datetime.date.today() + datetime.timedelta(2)
        expected_date_string = "{}-{}-{}".format(expected_date.year, expected_date.month,
                                                 expected_date.day)
        tag = terraform_config.generate_expire_on_tag()
        self.assertEqual(tag, expected_date_string)

        expected_date = datetime.date.today() + datetime.timedelta(1)
        expected_date_string = "{}-{}-{}".format(expected_date.year, expected_date.month,
                                                 expected_date.day)
        tag = terraform_config.generate_expire_on_tag(1)
        self.assertEqual(tag, expected_date_string)

        expected_date = datetime.date.today() + datetime.timedelta(100)
        expected_date_string = "{}-{}-{}".format(expected_date.year, expected_date.month,
                                                 expected_date.day)
        tag = terraform_config.generate_expire_on_tag(100)
        self.assertEqual(tag, expected_date_string)

    def test_is_placement_group_needed(self):
        """Test is_placement_group_needed()"""
        tfvars = {
            'mongod_instance_type': 'c3.8xlarge',
            'mongod_instance_count': 3,
            'mongos_instance_type': 'c3.8xlarge',
            'mongos_instance_count': 0,
            'configsvr_instance_type': 't1.micro',
            'configsvr_instance_count': 3
        }

        self.assertEqual(True, terraform_config.is_placement_group_needed('mongod', tfvars))
        self.assertEqual(False, terraform_config.is_placement_group_needed('mongos', tfvars))

        self.assertEqual(False, terraform_config.is_placement_group_needed('configsvr', tfvars))

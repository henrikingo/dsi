"""test file for terraform_env"""

# pylint: disable=invalid-name
from __future__ import print_function
import datetime
import logging
import os
import unittest
from mock import patch

import requests
import requests.exceptions
from testfixtures import LogCapture

from common import terraform_config


class TestTerraformConfiguration(unittest.TestCase):
    """To test terraform configuration class."""

    def setUp(self):
        ''' Save some common values '''
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

    def _test_configuration(self, tf_config, expected_output_string):
        json_string = tf_config.to_json(compact=True)
        self.assertEqual(json_string, expected_output_string)

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

    @patch('common.terraform_config.generate_runner')
    @patch('common.terraform_config.retrieve_runner_instance_id')
    def test_default(self, mock_retrieve_runner_instance_id, mock_generate_runner):
        """Test default terraform configuration, that is to update expire-on only."""
        mock_generate_runner.return_value = '111.111.111.111'
        mock_retrieve_runner_instance_id.return_value = 'i-0c2aad81dfac5ca6e'
        tf_config = terraform_config.TerraformConfiguration(
            use_config=False, now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        json_string = tf_config.to_json(compact=True)

        self.assertEqual(json_string, '{"expire_on":"2016-5-27",'
                         '"runner":"111.111.111.111",'
                         '"runner_instance_id":"i-0c2aad81dfac5ca6e",'
                         '"status":"running"}')

    @patch('common.terraform_config.generate_runner')
    @patch('common.terraform_config.retrieve_runner_instance_id')
    def test_mongod_instance(self, mock_retrieve_runner_instance_id, mock_generate_runner):
        """Test mongod instance parameters."""
        mock_generate_runner.return_value = '111.111.111.111'
        mock_retrieve_runner_instance_id.return_value = 'i-0c2aad81dfac5ca6e'
        tf_config = terraform_config.TerraformConfiguration(
            topology="test-cluster",
            use_config=False,
            now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        tf_config.define_instance(None, "mongod", 10, "c3.8xlarge")
        self._test_configuration(tf_config, '{"expire_on":"2016-5-27",'
                                 '"mongod_instance_count":10,'
                                 '"mongod_instance_placement_group":"yes",'
                                 '"mongod_instance_type":"c3.8xlarge",'
                                 '"runner":"111.111.111.111",'
                                 '"runner_instance_id":"i-0c2aad81dfac5ca6e",'
                                 '"status":"running",'
                                 '"topology":"test-cluster"}')

    @patch('common.terraform_config.generate_runner')
    @patch('common.terraform_config.retrieve_runner_instance_id')
    def test_large_cluster(self, mock_retrieve_runner_instance_id, mock_generate_runner):
        """Test cluster with mixed instances."""
        mock_generate_runner.return_value = '111.111.111.111'
        mock_retrieve_runner_instance_id.return_value = 'i-0c2aad81dfac5ca6e'
        tf_config = terraform_config.TerraformConfiguration(
            topology="test-cluster",
            use_config=False,
            now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))

        tf_config.define_instance(None, "mongos", 1, "m3.2xlarge")
        tf_config.define_instance(None, "mongod", 10, "c3.2xlarge")
        tf_config.define_instance(None, "configsvr", 3, "m3.xlarge")
        self._test_configuration(tf_config, '{"configsvr_instance_count":3,'
                                 '"configsvr_instance_placement_group":"no",'
                                 '"configsvr_instance_type":"m3.xlarge",'
                                 '"expire_on":"2016-5-27",'
                                 '"mongod_instance_count":10,'
                                 '"mongod_instance_placement_group":"yes",'
                                 '"mongod_instance_type":"c3.2xlarge",'
                                 '"mongos_instance_count":1,'
                                 '"mongos_instance_placement_group":"no",'
                                 '"mongos_instance_type":"m3.2xlarge",'
                                 '"runner":"111.111.111.111",'
                                 '"runner_instance_id":"i-0c2aad81dfac5ca6e",'
                                 '"status":"running",'
                                 '"topology":"test-cluster"}')

    @patch('common.terraform_config.generate_runner')
    @patch('common.terraform_config.retrieve_runner_instance_id')
    def test_no_placement_group(self, mock_retrieve_runner_instance_id, mock_generate_runner):
        """Test cluster with placement group."""
        mock_generate_runner.return_value = '111.111.111.111'
        mock_retrieve_runner_instance_id.return_value = 'i-0c2aad81dfac5ca6e'
        tf_config = terraform_config.TerraformConfiguration(
            topology="test-cluster",
            use_config=False,
            now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))

        tf_config.define_instance(None, "mongos", 10, "m3.2xlarge")
        self._test_configuration(tf_config, '{"expire_on":"2016-5-27",'
                                 '"mongos_instance_count":10,'
                                 '"mongos_instance_placement_group":"no",'
                                 '"mongos_instance_type":"m3.2xlarge",'
                                 '"runner":"111.111.111.111",'
                                 '"runner_instance_id":"i-0c2aad81dfac5ca6e",'
                                 '"status":"running",'
                                 '"topology":"test-cluster"}')

    def test_count_exception(self):
        """Test exception for invalid instance count."""
        tf_config = terraform_config.TerraformConfiguration("test-cluster", use_config=False)

        # test exception for wrong instance type
        with self.assertRaises(ValueError):
            tf_config.define_instance(None, "mongod", 10, "m4.2xlarge")

        with self.assertRaises(ValueError):
            tf_config.define_instance(None, "workload", 0, "c3.8xlarge")

    def test_generate_expire_on_tag(self):
        """Test expire-on tag generator."""
        tag = terraform_config.generate_expire_on_tag(
            now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))
        self.assertEqual(tag, "2016-5-27")

        tag = terraform_config.generate_expire_on_tag(
            now=datetime.datetime(2016, 5, 31, 7, 11, 49, 131998))
        self.assertEqual(tag, "2016-6-2")

        tag = terraform_config.generate_expire_on_tag(
            now=datetime.datetime(2016, 12, 31, 7, 11, 49, 131998))
        self.assertEqual(tag, "2017-1-2")

    def test_placement_group_mapping(self):
        """Test proper mapping from instance type to whether support placement group."""

        self.assertEqual(True, terraform_config.support_placement_group("c3.8xlarge"))
        self.assertEqual(True, terraform_config.support_placement_group("m4.xlarege"))

        self.assertEqual(False, terraform_config.support_placement_group("m3.2xlarege"))

    @patch('common.terraform_config.generate_runner')
    @patch('common.terraform_config.retrieve_runner_instance_id')
    def test_provisioning_file(self, mock_retrieve_runner_instance_id, mock_generate_runner):
        """Test cluster with provisioning file overwrite."""
        mock_generate_runner.return_value = '111.111.111.111'
        mock_retrieve_runner_instance_id.return_value = 'i-0c2aad81dfac5ca6e'
        old_dir = os.getcwd()
        os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/artifacts')

        tf_config = terraform_config.TerraformConfiguration(
            topology="test-cluster", now=datetime.datetime(2016, 5, 25, 7, 11, 49, 131998))

        self._test_configuration(tf_config, '{"availability_zone":"us-west-2b",'
                                 '"cluster_name":"test-cluster",'
                                 '"configsvr_instance_count":5,'
                                 '"configsvr_instance_placement_group":"no",'
                                 '"configsvr_instance_type":"m3.4xlarge",'
                                 '"expire_on":"2016-5-28",'
                                 '"key_file":"../../keys/aws.pem",'
                                 '"key_name":"serverteam-perf-ssh-key",'
                                 '"mongod_instance_count":15,'
                                 '"mongod_instance_placement_group":"yes",'
                                 '"mongod_instance_type":"c3.8xlarge",'
                                 '"mongos_instance_count":3,'
                                 '"mongos_instance_placement_group":"yes",'
                                 '"mongos_instance_type":"c3.8xlarge",'
                                 '"owner":"serverteam-perf@10gen.com",'
                                 '"region":"us-west-2",'
                                 '"runner":"111.111.111.111",'
                                 '"runner_instance_id":"i-0c2aad81dfac5ca6e",'
                                 '"status":"running",'
                                 '"topology":"test-cluster",'
                                 '"workload_instance_count":1,'
                                 '"workload_instance_placement_group":"yes",'
                                 '"workload_instance_type":"c3.8xlarge"}')
        os.chdir(old_dir)

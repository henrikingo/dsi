"""
Utility function.
"""
import ConfigParser
import os
import errno
import logging

LOG = logging.getLogger(__name__)


def mkdir_p(path):
    """
    Make the directory and all missing parents (like mkdir -p)
    :type path: string the directory path
    """
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def touch(filename):
    """
    Create an empty file (like shell touch command). It will not
    create directories
    :type filename: string the full path to the filename
    """
    open(filename, 'a').close()


def read_aws_credentials(config):
    """
    Read AWS credentials into a config object
    """
    aws_config = {}
    # if we can read variables out of the ~/.aws/credentials file, do so
    read_aws_credentials_file(aws_config)

    # environment variables should supersede config file reading
    read_env_vars(aws_config)
    if 'runtime_secret' in config:
        if 'aws_access_key' in config['runtime_secret']:
            aws_config['aws_access_key'] = config['runtime_secret']['aws_access_key']
        if 'aws_secret_key' in config['runtime_secret']:
            aws_config['aws_secret_key'] = config['runtime_secret']['aws_secret_key']

    print aws_config
    if 'aws_access_key' not in aws_config or 'aws_secret_key' not in aws_config:
        LOG.critical('AWS credentials not found. Please ensure that they are present in '
                     '~/.aws/credentials or are present in your environment as AWS_ACCESS_KEY_ID'
                     ' and AWS_SECRET_ACCESS_KEY.')
        assert False

    return aws_config['aws_access_key'], aws_config['aws_secret_key']


def read_aws_credentials_file(aws_config):
    """
    Read AWS credentials from the 'default' field of ~/.aws/credentials, if it exists
    """
    defaults = {}
    credential_path = os.path.expanduser('~/.aws/credentials')
    section = 'default'
    config_parser = ConfigParser.ConfigParser(defaults=defaults)
    config_parser.read(credential_path)
    if config_parser.has_section(section):
        aws_config['aws_access_key'] = config_parser.get(section, 'aws_access_key_id')
        aws_config['aws_secret_key'] = config_parser.get(section, 'aws_secret_access_key')


def read_env_vars(aws_config):
    """
    Read AWS access key id and and secret access key from environment variables
    """
    if 'AWS_ACCESS_KEY_ID' in os.environ:
        aws_config['aws_access_key'] = os.environ.get('AWS_ACCESS_KEY_ID')
    if 'AWS_SECRET_ACCESS_KEY' in os.environ:
        aws_config['aws_secret_key'] = os.environ.get('AWS_SECRET_ACCESS_KEY')

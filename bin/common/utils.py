"""
Utility function.
"""
import configparser as ConfigParser
import os
import errno
import logging
import re
import subprocess

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


def get_dsi_path():
    """Get the Path to this source tree

    :returns: The path to this source tree
    :rtype: str

    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_dsi_bin_dir():
    """Get the path to the bin directory in this source tree

    :returns: The path to the bin directory in this source tree
    :rtype: str

    """
    return os.path.join(get_dsi_path(), 'bin')


class TerraformNotFound(IOError):
    """
    Raised if terraform binary not found.

    This should be unlikely, since bootstrap.py checks that it existed when we started.
    """
    def __init__(self):
        message = "Did not find terraform in PATH nor current directory."
        super(TerraformNotFound, self).__init__(message)


def find_terraform(work_directory="."):
    """
    Find terraform executable.

    :param str work_directory: Like "current directory", but in bootstrap.py we're not yet in it.
    :returns: Path to terraform executable file (not dir).
    """
    if "TERRAFORM" in os.environ:
        return os.environ['TERRAFORM']
    elif os.path.isfile('terraform'):
        return os.path.join(work_directory, 'terraform')
    else:
        # Find terraform in path
        try:
            return subprocess.check_output(['which', 'terraform'], encoding='utf-8').strip()
        except subprocess.CalledProcessError:
            raise TerraformNotFound()
        except OSError:
            raise TerraformNotFound()


def print_bootstrap_configs():
    """
    Do listdir on configurations/*, and print the parts of the filenames used in bootstrap.yml.
    """
    col_width = 32
    line_width = 100
    conf_dir = os.path.join(os.path.dirname(get_dsi_bin_dir()), "configurations")
    dsi_modules = [
        'infrastructure_provisioning', 'workload_setup', 'mongodb_setup', 'test_control', 'analysis'
    ]
    print("Available canned configurations that you can use in bootstrap.yml:")
    print("See {} for details.\n\n".format(conf_dir))
    for module in dsi_modules:
        sub_dir = os.path.join(conf_dir, module)
        prog = re.compile(r'^' + module + r'\.(.+)\.yml$')
        found = []
        for file_name in os.listdir(sub_dir):
            result = prog.match(file_name)
            if result:
                name_part = result.group(1)
                found.append(name_part)
        found.sort()

        # mongodb_setup:
        output = "{}:\n\n".format(module)
        count = 1
        for word in found:
            # replica + padding
            output += word.ljust(col_width) + " "
            if len(word) > col_width - 1:
                # If word was longer than col_width, pad another column.
                # Except if at last column.
                if count % (line_width // col_width) != 0:
                    output += " " * (col_width - len(word) % col_width + 1)
                    count += 1
            if count % (line_width // col_width) == 0:
                output += "\n"
            count += 1
        output += "\n\n"
        print(output)

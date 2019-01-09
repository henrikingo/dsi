"""
Perform initialization required from change_point command.
"""
import os

import click
import structlog
import yaml

from signal_processing.keyring.mongo_keyring import prompt_for_credentials, \
    save_credentials_to_keyring, new_mongo_client

import signal_processing.commands.helpers as helpers

LOG = structlog.getLogger(__name__)

APP_NAME = os.environ.get('DSI_APP_NAME', 'change-points')
DEFAULT_LOG_FILE = os.path.join('/', 'tmp', '{}.log'.format(APP_NAME))
DEFAULT_CONFIG_FILE = click.get_app_dir(APP_NAME, roaming=True, force_posix=True)


def validate_mongo_connection(mongo_uri, credentials):
    """
    Attempt to connect to the specified mongo database.

    :param mongo_uri: mongo host to connect to.
    :param credentials: credentials to connect with.
    """
    mongo_client = new_mongo_client(mongo_uri, credentials)
    db = mongo_client.get_database()
    coll = db.get_collection(helpers.CHANGE_POINTS)
    coll.find_one()


def write_configuration(configuration, destination):
    """
    Write the provided configuration to the file specified.

    :param configuration: configuration data to write.
    :param destination: file to write to.
    """
    with open(destination, 'w') as out:
        out.write(yaml.dump(configuration, default_flow_style=False, Dumper=yaml.SafeDumper))


def print_preamble():
    """Display preamble message to the user."""
    click.echo("""
In order to use the change-points CLI, you must have a valid Atlas DB username / password. Adding a
DB user is covered in the Performance Build Baron document in the 'Add yourself to the Atlas 
Project' section (https://goo.gl/VoGF7D).

If you do not yet have access to the Atlas Database then please take the time to read this section
and obtain valid database credentials.
""")

    click.secho('You will not be able to proceed without it.', fg='yellow', bold=True)


def get_configuration():
    """Prompt user for configuration values."""
    config = {}

    log_file = click.prompt('Where should log output go', default=DEFAULT_LOG_FILE)
    config['logfile'] = log_file

    mongo_uri = click.prompt(
        'What is the mongo uri for performance data', default=helpers.DEFAULT_MONGO_URI)
    config['mongo_uri'] = mongo_uri

    auth_needed = click.confirm('Does this uri need authentication', default=True)
    if auth_needed:
        click.secho(
            'If you do not know what credentials are needed for the performance cluster, ',
            fg='yellow')
        click.secho('please ask in the #perf-build-baroning channel in slack.', fg='yellow')
        use_keyring = click.confirm(
            'Would you like to store mongo credentials in the system keyring', default=True)
        if use_keyring:
            config['auth_mode'] = 'keyring'
            creds = prompt_for_credentials()
            validate_mongo_connection(mongo_uri, creds)
            save_credentials_to_keyring(creds)
        else:
            config['auth_mode'] = 'prompt'
            click.secho(
                'System keyring is NOT being used, credentials will be require each run.',
                fg='yellow',
                bold=True)

    return config


@click.command(name='init')
@click.option(
    '--target-file',
    default=DEFAULT_CONFIG_FILE,
    help='File to write configuration to (defaults to "{}").'.format(DEFAULT_CONFIG_FILE))
def init_command(target_file):
    """
    Perform initialization steps required to run the change-points command.

    The user will be prompted for any required information not specified via command line
    arguments.
    """
    if os.path.exists(target_file):
        click.confirm(
            '{file} already exists, continue (overriding existing file)?'.format(file=target_file),
            abort=True)

    print_preamble()

    config = get_configuration()
    write_configuration(config, target_file)

"""
Handle keyring import.
"""
import structlog
LOG = structlog.getLogger(__name__)

try:
    import keyring
    keyring.get_password('jira', 'dummy')
    from signal_processing.keyring.keyring_impl import Keyring
# pylint: disable=bare-except
except:
    LOG.debug('no keyring implementation available, fall back to NoopKeyring.', exc_info=1)
    from signal_processing.keyring.keyring_impl import NoopKeyring as Keyring

"""Credentials (username/password) for various systems."""
import ast


class Credentials(object):
    """Basic authentication credentials (username/password)."""

    # pylint: disable=too-few-public-methods

    def __init__(self, username, password):
        """Create a Credentials from a username and password."""
        self.username = username
        self.password = password

    def __eq__(self, other):
        if type(other) is type(self):
            return other.username == self.username and other.password == self.password
        return False

    def __str__(self):
        return '({}, {})'.format(self.username, self._redact_password(self.password))

    @staticmethod
    def _redact_password(password):
        """
        Redact the password.

        :param password: The password to redact.
        :type password: str or None.
        :return: A redacted password.
        """

        if password is not None:
            return '*' * min(8, max(8, len(password)))
        return password

    def encode(self):
        """
        Encode the credentials.

        :return: A string of encoded credentials.
        """
        return '{}'.format([self.username, self.password])

    @staticmethod
    def decode(credentials):
        """
        Decode the credentials

        :param str credentials: The encoded Jira credentials.
        :return: A JiraCredentials instance.
        """
        if credentials is not None:
            username, password = ast.literal_eval(credentials)
            return Credentials(username, password)
        return Credentials(None, None)

"""
Thread to execute during_test commands at given times during a test.

during_test commands are like the other pre/post commands, but an additional `at:` key defines
a point in time when they should be executed. See docs/config-specs/test_control.py for more
information.
"""
import threading
import time

import duration
import structlog

from common.command_runner import run_pre_post_commands, EXCEPTION_BEHAVIOR
import common.config

LOG = structlog.get_logger(__name__)


def start(test, config):
    """
    Start a thread that will execute during_test commands at given times, if any.

    :param ConfigDict config: The DSI configuration.
    :param ConfigDict test: The configuration for the current test.
    :return: A method that will stop the thread started by this method.
    """
    thread = DuringTestThread(test, config)
    thread.daemon = True
    thread.start()
    return thread.stop


class DuringTestThread(threading.Thread):
    """
    Thread object to execute during_test commands
    """
    def __init__(self, test, config):
        """
        Create a thread object that will execute during_test commands at given times, if any.

        :param ConfigDict config: The DSI configuration.
        :param ConfigDict test: The configuration for the current test.
        :raises InvalidDsiCommand: For malformed command structures.
        """
        threading.Thread.__init__(self)
        LOG.debug("DuringTestThread.__init__()")
        self._stop_signal = False
        self.test = test
        self.config = config
        self.commands = []
        self.start_time = time.time()
        self._parse_commands()

    def stop(self):
        """
        Signal this thread to stop.

        Thread will stop as soon as it checks self._stop_signal
        """
        if self.is_alive():
            LOG.info("Stopping during_test thread...")
            self._stop_signal = True
            self.join()
            LOG.info("Stopped during_test thread.")
        else:
            LOG.debug("DuringTestThread.stop(): Already stopped.")

    def run(self):
        """
        Main method for the thread.
        """
        for next_command in self.commands:
            at_seconds = next_command.pop('at_seconds')
            # Can't just sleep, because we need to periodically check self._stop_signal
            while time.time() < at_seconds:
                if self._stop_signal:
                    LOG.warning(
                        "Stopping during_test thread even if some commands are still not executed")
                    return
                time.sleep(1)

            # run_pre_post_commands() will complain about extra top level fields.
            # Note: I didn't remove this earlier because this is nice to keep around for
            # debuggability.
            del next_command['at']
            self.run_command(next_command)

        LOG.debug("during_test thread exiting, no more commands scheduled")

    def run_command(self, command):
        """
        Run a single DSI command.

        :param dict command: Any of the commands that can be used in the pre_task, pre_test, etc
                             configuration blocks.
        """
        fake_command_list = [{'during_test': [command]}]
        # It would be better to use EXCEPTION_BEHAVIOR.RERAISE, but then we would want to
        # reraise the exception in the main thread, and that seems complex.
        # TODO: Store exceptions in a queue which main thread can check periodically.
        run_pre_post_commands("during_test", fake_command_list, self.config,
                              EXCEPTION_BEHAVIOR.CONTINUE, self.test['id'])

    def _parse_commands(self):
        """
        Get mongodb_setup.during_test, test_control.during_test, test.during_test, if any.
        """
        raw_commands = self.config['mongodb_setup'].get('during_test', [])
        raw_commands += self.config['test_control'].get('during_test', [])
        raw_commands += self.test.get('during_test', [])
        if raw_commands:
            self._sort_command_times(raw_commands)

    def _sort_command_times(self, raw_commands):
        """
        Sort commands by the time given in their at: field.

        :param list(ConfigDict) raw_commands: A list of "pre post" command objects from DSI config.
        """
        commands_by_time = {}
        for raw_command in raw_commands:
            command = raw_command
            if isinstance(raw_command, common.config.ConfigDict):
                command = raw_command.as_dict()

            if not 'at' in command:
                raise InvalidDsiCommand("at missing", command)
            LOG.debug("found during_test command to schedule", at=command['at'])
            command['at_seconds'] = self.start_time + duration.to_seconds(command['at'])
            commands_by_time[command['at_seconds']] = command

        for at_seconds in sorted(commands_by_time.keys()):
            self.commands.append(commands_by_time[at_seconds])


class InvalidDsiCommand(Exception):
    """Indicates invalid during_test object in DSI configuration."""
    def __init__(self, reason, command):
        self.command = command
        message = "Invalid during_test command, {}: {}".format(reason, command)
        Exception.__init__(message)

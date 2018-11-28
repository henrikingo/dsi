"""
RemoteHost implementation that uses jasper gRPC (https://github.com/mongodb/jasper).

"""

import logging
import os

import grpc
import grpc._channel as grpc_channel  # pylint: disable=protected-access

import pkg_resources

import common.remote_host

LOG = logging.getLogger(__name__)
# This stream only log error or above messages
ERROR_ONLY = logging.getLogger('error_only')

DEFAULT_JASPER_PORT = 2286

DEFAULT_REMOTE_HOME_DIR = '/home/ec2-user'


# pylint: disable=too-few-public-methods
class RemoteJasperHost(common.remote_host.RemoteHost):
    """
    Represents a remote host that executes commands through gRPC to a Jasper server.

    Note that ssh credentials are still needed to do remote operations
    """
    has_run_protoc = False

    def __init__(self, hostname, username, pem_file, mongodb_auth_settings=None):
        super(RemoteJasperHost, self).__init__(hostname, username, pem_file, mongodb_auth_settings)

        if not self.has_run_protoc:
            self._run_protoc()
            self.has_run_protoc = True

        import jasper.jasper_pb2_grpc as jasper_grpc
        import jasper.jasper_pb2 as jasper_pb

        self.jasper_grpc = jasper_grpc
        self.jasper_pb = jasper_pb

        conn_string = '%s:%d' % (hostname, DEFAULT_JASPER_PORT)
        LOG.info('Creating gRPC channel to host %s', conn_string)
        self.channel = grpc.insecure_channel(conn_string)
        self.stub = self.jasper_grpc.JasperProcessManagerStub(self.channel)

    # pylint: disable=too-many-arguments
    def exec_command(self,
                     argv,
                     stdout=None,
                     stderr=None,
                     get_pty=False,
                     max_time_ms=None,
                     no_output_timeout_ms=None,
                     quiet=False):
        """
        Execute a command on a remote host through Jasper. Return the exit code.
        """

        if quiet:
            logger = ERROR_ONLY
        else:
            logger = LOG

        # Right now many options are not supported in Jasper. We warn the user but don't
        # error out.
        if no_output_timeout_ms is not None:
            logger.warning("no_output_timeout_ms is not supported on RemoteJasperHost")

        if max_time_ms is not None:
            logger.warning("max_time_ms is not supported on RemoteJasperHost")

        if get_pty is not False:
            logger.warning("get_pty is not supported on RemoteJasperHost")

        if stdout is not None:
            logger.warning('stdout is not supported on RemoteJasperHost')

        if stderr is not None:
            logger.warning('stderr is not supported on RemoteJasperHost')

        if not isinstance(argv, list):
            raise ValueError("Argument must be a nonempty list")

        return self._do_exec_command(argv, logger)

    def _do_exec_command(self, argv, logger):
        create_options = self.jasper_pb.CreateOptions(
            args=argv,
            working_directory=DEFAULT_REMOTE_HOME_DIR,
            environment={},
            override_environ=False,
            timeout_seconds=0,
            output=self._get_output_options())

        logger.info('Creating process: %r', create_options)
        proc_info = self.stub.Create(create_options)
        self._debug_proc_info(logger, proc_info)
        logger.info('Created process with info: %r', proc_info)

        if not proc_info.running:
            return proc_info.exit_code

        jasper_pid = self.jasper_pb.JasperProcessID(value=proc_info.id)

        try:
            wait_outcome = self.stub.Wait(jasper_pid)
        except grpc_channel._Rendezvous as e:  # pylint: disable=protected-access
            # Jasper can fail with "operation failed" when waiting on a process that has
            # already terminated.
            logger.error(e)
            return 0

        if not wait_outcome.success:
            logger.error('Failed to wait for process: %r, exit code: %r, error: %r', argv,
                         wait_outcome.exit_code, wait_outcome.text)
        return wait_outcome.exit_code

    def _get_output_options(self):
        log_type = self.jasper_pb.LogType.Value('LOGINHERIT')
        log_format = self.jasper_pb.LogFormat.Value('LOGFORMATDEFAULT')
        log_options = self.jasper_pb.LogOptions(format=log_format)

        logger = self.jasper_pb.Logger(log_type=log_type, log_options=log_options)
        logger_opts = [logger]
        return self.jasper_pb.OutputOptions(loggers=logger_opts)

    @staticmethod
    def _run_protoc():
        """
        Run the "protoc" command line tool to generate teh Python jasper client from jasper.proto.
        Do this every time this file is loaded to ensure we always have the correct version
        of the Python client (At the expense of some redundant computation time).
        """
        from grpc_tools import protoc

        proto_include = pkg_resources.resource_filename('grpc_tools', '_proto')

        # Use path relative to this file because CWD changes for tests.
        proto_out = os.path.join(os.path.dirname(__file__), '..', 'jasper')
        protoc.main([
            protoc.__file__, '--python_out', proto_out, '--grpc_python_out', proto_out,
            '--proto_path', proto_out,
            os.path.join(proto_out, 'jasper.proto'), '--proto_path', proto_include
        ])

    @staticmethod
    def _debug_proc_info(logger, proc_info):
        logger.debug('proc_info.successful: %r', proc_info.successful)
        logger.debug('proc_info.complete: %r', proc_info.complete)
        logger.debug('proc_info.timedout: %r', proc_info.timedout)
        logger.debug('proc_info.running: %r', proc_info.running)
        logger.debug('proc_info.host_id: %s', proc_info.host_id)
        logger.debug('proc_info.pid: %s', proc_info.pid)
        logger.debug('proc_info: %r', proc_info)

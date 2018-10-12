# (C) Datadog, Inc. 2010-2016
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)

# stdlib
import urlparse
import os, subprocess
from contextlib import nested
import tempfile
import signal

# 3rd party
import requests

# project
from checks import AgentCheck
from util import headers
from config import _is_affirmative

_JVM_DEFAULT_MAX_MEMORY_ALLOCATION = " -Xmx200m"
_JVM_DEFAULT_SD_MAX_MEMORY_ALLOCATION = " -Xmx512m"
_JVM_DEFAULT_INITIAL_MEMORY_ALLOCATION = " -Xms50m"
JMXFETCH_MAIN_CLASS = "org.datadog.jmxfetch.App"
JMX_COLLECT_COMMAND = 'collect'
JMX_LIST_JVMS = 'list_jvms'
JMX_LIST_COMMANDS = {
    'list_everything': 'List every attributes available that has a type supported by JMXFetch',
    'list_collected_attributes': 'List attributes that will actually be collected by your current instances configuration',
    'list_matching_attributes': 'List attributes that match at least one of your instances configuration',
    'list_not_matching_attributes': "List attributes that don't match any of your instances configuration",
    'list_limited_attributes': "List attributes that do match one of your instances configuration but that are not being collected because it would exceed the number of metrics that can be collected",
    JMX_LIST_JVMS: "List available Java virtual machines on the system using the Attach API",
    JMX_COLLECT_COMMAND: "Start the collection of metrics based on your current configuration and display them in the console"
}

JMX_LAUNCH_FILE = 'jmx.launch'


class Tomcat(AgentCheck):
    """Tracks basic connection/requests/workers metrics

    See http://httpd.apache.org/docs/2.2/mod/mod_status.html for more details
    """

    reporter = 'reporter.py'

    def __init__(self, name, init_config, agentConfig, instances=None):
        #print 'agent check', name, init_config, agentConfig, instances
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self.currtent_dir = os.getcwd()
        self._process = None
        self._running = False

    def check(self, instance):
        # print 'current path', self.currtent_dir
        # print 'instance', instance

        # if self._running:
        if self.check_process_exists():
            print 'check already start!'
        else:
            cmd = self.get_check_cmd_by_instance(instance)
            print 'exec ', cmd
            self.execute(cmd)
        return

    @staticmethod
    def check_process_exists():
        try:
            subprocess.check_output(["pgrep", "-f", ".*org\.datadog\.jmxfetch\.App.*"])
            return True
        except Exception:
            return False


    def get_check_cmd_by_instance(self, instance):
        java_cmd = instance['java_bin_path'] + '/java'
        java_run_opts = ""

        classpath = self.currtent_dir + '/checks/libs/jmxfetch.jar'

        conf_path = self.currtent_dir + '/conf.d/'
        log_path = self.currtent_dir + '/log/jmxfetch.log'

        subprocess_args = [
            java_cmd,
            '-classpath',
            classpath,
            JMXFETCH_MAIN_CLASS,
            '--check', 'tomcat.yaml',
            '--check_period', '60000',
            '--conf_directory', conf_path,
            '--log_location ', log_path,
            '--reporter', 'console',
            'collect'
        ]

        if "Xmx" not in java_run_opts and "XX:MaxHeapSize" not in java_run_opts:
            java_run_opts += _JVM_DEFAULT_MAX_MEMORY_ALLOCATION
        # Specify the initial memory allocation pool for the JVM
        if "Xms" not in java_run_opts and "XX:InitialHeapSize" not in java_run_opts:
            java_run_opts += _JVM_DEFAULT_INITIAL_MEMORY_ALLOCATION

        for opt in java_run_opts.split():
            subprocess_args.insert(1, opt)

        return subprocess_args

    def execute(self, process_args, redirect_std_streams=None, env=None):
        try:
            with nested(tempfile.TemporaryFile(), tempfile.TemporaryFile()) as (stdout_f, stderr_f):
                process = subprocess.Popen(
                    process_args,
                    close_fds=not redirect_std_streams,  # only set to True when the streams are not redirected, for WIN compatibility
                    stdout=stdout_f if redirect_std_streams else None,
                    stderr=stderr_f if redirect_std_streams else None,
                    env=env
                )
                self._process = process
                self._running = True

                # Register SIGINT and SIGTERM signal handlers
                #self.register_signal_handlers()

                # Wait for process to return
                # self._process.wait()
                # self._running = False

            return self._process.returncode
        except Exception:
            raise

    def terminate(self):
        if self._process:
            ret_code = self._process.terminate()
            print 'jmxfetch process code', ret_code


    def _handle_sigterm(self, signum, frame):
        # Terminate jmx process on SIGTERM signal
        #log.debug("Caught sigterm. Stopping subprocess.")
        self.terminate()

    def register_signal_handlers(self):
        """
        Enable SIGTERM and SIGINT handlers
        """
        try:
            # Gracefully exit on sigterm
            signal.signal(signal.SIGTERM, self._handle_sigterm)

            # Handle Keyboard Interrupt
            signal.signal(signal.SIGINT, self._handle_sigterm)

        except ValueError:
            pass
            #log.exception("Unable to register signal handlers.")




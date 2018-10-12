# (C) Datadog, Inc. 2010-2016
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)

# stdlib
import ConfigParser
from cStringIO import StringIO
import glob
import imp
import os
import inspect
import itertools
import logging
import logging.config
import logging.handlers
from optparse import OptionParser, Values
import re
import string
import sys
import traceback

# 3p
import simplejson as json

# project
from util import check_yaml, config_to_yaml
from utils.sdk import load_manifest

# CONSTANTS
AGENT_VERSION='1.0.0'
DATADOG_CONF = 'dcos_dd.conf'
UNIX_CONFIG_PATH = './etc'
LOGGING_MAX_BYTES = 10 * 1024 * 1024
SDK_INTEGRATIONS_DIR = 'integrations'

log = logging.getLogger(__name__)

OLD_STYLE_PARAMETERS = [
    ('apache_status_url', "apache"),
    ('cacti_mysql_server', "cacti"),
    ('couchdb_server', "couchdb"),
    ('elasticsearch', "elasticsearch"),
    ('haproxy_url', "haproxy"),
    ('hudson_home', "Jenkins"),
    ('memcache_', "memcached"),
    ('mongodb_server', "mongodb"),
    ('mysql_server', "mysql"),
    ('nginx_status_url', "nginx"),
    ('postgresql_server', "postgres"),
    ('redis_urls', "redis"),
    ('varnishstat', "varnish"),
    ('WMI', "WMI"),
]

class PathNotFound(Exception):
    pass


def skip_leading_wsp(f):
    "Works on a file, returns a file-like object"
    return StringIO("\n".join(map(string.strip, f.readlines())))


def _config_path(directory):
    path = os.path.join(directory, DATADOG_CONF)
    if os.path.exists(path):
        return path
    raise PathNotFound(path)


def _confd_path(directory):
    path = os.path.join(directory, 'conf.d')
    if os.path.exists(path):
        return path
    raise PathNotFound(path)


def _checksd_path(directory):
    path_override = os.environ.get('CHECKSD_OVERRIDE')
    if path_override and os.path.exists(path_override):
        return path_override

    # this is deprecated in testing on versions after SDK (5.12.0)
    path = os.path.join(directory, 'checks.d')
    if os.path.exists(path):
        return path
    raise PathNotFound(path)

def _is_affirmative(s):
    if s is None:
        return False
    if isinstance(s, int):
        return bool(s)
    return s.lower() in ('yes', 'true', '1')

def get_config_path(cfg_path=None):
    # Check if there's an override and if it exists
    if cfg_path is not None and os.path.exists(cfg_path):
        return cfg_path

    # Check if there's a config stored in the current agent directory
    try:
        path = os.path.realpath(__file__)
        path = os.path.dirname(path)
        return _config_path(path)
    except PathNotFound as e:
        pass

    # Check for an OS-specific path, continue on not-found exceptions
    bad_path = ''
    try:
        return _config_path(UNIX_CONFIG_PATH)
    except PathNotFound as e:
        if len(e.args) > 0:
            bad_path = e.args[0]

    # If all searches fail, exit the agent with an error
    sys.stderr.write("Please supply a configuration file at %s or in the directory where "
                     "the Agent is currently deployed.\n" % bad_path)
    sys.exit(3)

def remove_empty(string_array):
    return filter(lambda x: x, string_array)


def get_confd_path():
    try:
        cur_path = os.path.dirname(os.path.realpath(__file__))
        return _confd_path(cur_path)
    except PathNotFound as e:
        pass

    bad_path = ''
    try:
        return _confd_path(UNIX_CONFIG_PATH)
    except PathNotFound as e:
        if len(e.args) > 0:
            bad_path = e.args[0]

    raise PathNotFound(bad_path)


def get_checksd_path():
    cur_path = os.path.dirname(os.path.realpath(__file__))
    return _checksd_path(cur_path)

def get_sdk_integrations_path(osname=None):
    if os.environ.get('INTEGRATIONS_DIR'):
        if os.environ.get('TRAVIS'):
            path = os.environ['TRAVIS_BUILD_DIR']
        elif os.environ.get('CIRCLECI'):
            path = os.path.join(
                os.environ['HOME'],
                os.environ['CIRCLE_PROJECT_REPONAME']
            )
        elif os.environ.get('APPVEYOR'):
            path = os.environ['APPVEYOR_BUILD_FOLDER']
        else:
            cur_path = os.environ['INTEGRATIONS_DIR']
            path = os.path.join(cur_path, '..') # might need tweaking in the future.
    else:
        cur_path = os.path.dirname(os.path.realpath(__file__))
        path = os.path.join(cur_path, '..', SDK_INTEGRATIONS_DIR)

    if os.path.exists(path):
        return path
    raise PathNotFound(path)

def _get_check_class(check_name, check_path):
    '''Return the corresponding check class for a check name if available.'''
    from checks import AgentCheck
    check_class = None
    try:
        check_module = imp.load_source('checksd_%s' % check_name, check_path)
    except Exception as e:
        traceback_message = traceback.format_exc()
        # There is a configuration file for that check but the module can't be imported
        log.exception('Unable to import check module %s.py from checks.d' % check_name)
        return {'error': e, 'traceback': traceback_message}

    # We make sure that there is an AgentCheck class defined
    check_class = None
    classes = inspect.getmembers(check_module, inspect.isclass)
    for _, clsmember in classes:
        if clsmember == AgentCheck:
            continue
        if issubclass(clsmember, AgentCheck):
            check_class = clsmember
            if AgentCheck in clsmember.__bases__:
                continue
            else:
                break
    return check_class


def _file_configs_paths(agentConfig):
    """ Retrieve all the file configs and return their paths
    """
    try:
        confd_path = get_confd_path()
        all_file_configs = glob.glob(os.path.join(confd_path, '*.yaml'))
        all_default_configs = glob.glob(os.path.join(confd_path, '*.yaml.default'))
    except PathNotFound as e:
        log.error("No conf.d folder found at '%s' or in the directory where the Agent is currently deployed.\n" % e.args[0])
        sys.exit(3)

    if all_default_configs:
        current_configs = set([_conf_path_to_check_name(conf) for conf in all_file_configs])
        for default_config in all_default_configs:
            if not _conf_path_to_check_name(default_config) in current_configs:
                all_file_configs.append(default_config)

    return all_file_configs


def _conf_path_to_check_name(conf_path):
    f = os.path.splitext(os.path.split(conf_path)[1])
    if f[1] and f[1] == ".default":
        f = os.path.splitext(f[0])
    return f[0]


def get_checks_places(agentConfig):
    """ Return a list of methods which, when called with a check name, will each return a check path to inspect
    """
    try:
        checksd_path = get_checksd_path()
    except PathNotFound as e:
        log.error(e.args[0])
        sys.exit(3)

    places = [lambda name: (os.path.join(agentConfig['additional_checksd'], '%s.py' % name), None)]

    try:
        sdk_integrations = get_sdk_integrations_path()
        places.append(lambda name: (os.path.join(sdk_integrations, name, 'check.py'),
                                    os.path.join(sdk_integrations, name, 'manifest.json')))
    except PathNotFound:
        log.debug('No sdk integrations path found')

    places.append(lambda name: (os.path.join(checksd_path, '%s.py' % name), None))
    return places


def _load_file_config(config_path, check_name, agentConfig):
    try:
        check_config = check_yaml(config_path)
    except Exception as e:
        log.exception("Unable to parse yaml config in %s" % config_path)
        traceback_message = traceback.format_exc()
        return False, None, {check_name: {'error': str(e), 'traceback': traceback_message, 'version': 'unknown'}}
    return True, check_config, {}


def get_valid_check_class(check_name, check_path):
    check_class = _get_check_class(check_name, check_path)

    if not check_class:
        log.error('No check class (inheriting from AgentCheck) found in %s.py' % check_name)
        return False, None, {}
    # this means we are actually looking at a load failure
    elif isinstance(check_class, dict):
        return False, None, {check_name: check_class}

    return True, check_class, {}


def _initialize_check(check_config, check_name, check_class, agentConfig, manifest_path):
    init_config = check_config.get('init_config') or {}
    instances = check_config['instances']
    try:
        try:
            check = check_class(check_name, init_config=init_config,
                                agentConfig=agentConfig, instances=instances)
        except TypeError as e:
            # Backwards compatibility for checks which don't support the
            # instances argument in the constructor.
            check = check_class(check_name, init_config=init_config,
                                agentConfig=agentConfig)
            check.instances = instances

        if manifest_path:
            check.set_manifest_path(manifest_path)
        check.set_check_version(load_manifest(manifest_path))
    except Exception as e:
        log.exception('Unable to initialize check %s' % check_name)
        traceback_message = traceback.format_exc()
        manifest = load_manifest(manifest_path)
        if manifest is not None:
            check_version = '{core}:{vers}'.format(core='unknown',
                                                   vers=manifest.get('version', 'unknown'))
        else:
            check_version = AGENT_VERSION

        return {}, {check_name: {'error': e, 'traceback': traceback_message, 'version': check_version}}
    else:
        return {check_name: check}, {}


def _update_python_path(check_config):
    # Add custom pythonpath(s) if available
    if 'pythonpath' in check_config:
        pythonpath = check_config['pythonpath']
        if not isinstance(pythonpath, list):
            pythonpath = [pythonpath]
        sys.path.extend(pythonpath)


def validate_sdk_check(manifest_path):
    max_validated = min_validated = False
    try:
        with open(manifest_path, 'r') as fp:
            manifest = json.load(fp)
            current_version = _version_string_to_tuple(get_version())
            for maxfield in MANIFEST_VALIDATION['max']:
                max_version = manifest.get(maxfield)
                if not max_version:
                    continue

                max_validated = _version_string_to_tuple(max_version) >= current_version
                break

            for minfield in MANIFEST_VALIDATION['min']:
                min_version = manifest.get(minfield)
                if not min_version:
                    continue

                min_validated = _version_string_to_tuple(min_version) <= current_version
                break
    except IOError:
        log.debug("Manifest file (%s) not present." % manifest_path)
    except json.JSONDecodeError:
        log.debug("Manifest file (%s) has badly formatted json." % manifest_path)
    except ValueError:
        log.debug("Versions in manifest file (%s) can't be validated.", manifest_path)

    return (min_validated and max_validated)


def load_check_from_places(check_config, check_name, checks_places, agentConfig):
    '''Find a check named check_name in the given checks_places and try to initialize it with the given check_config.
    A failure (`load_failure`) can happen when the check class can't be validated or when the check can't be initialized. '''
    load_success, load_failure = {}, {}
    for check_path_builder in checks_places:
        check_path, manifest_path = check_path_builder(check_name)
        # The windows SDK function will return None,
        # so the loop should also continue if there is no path.
        if not (check_path and os.path.exists(check_path)):
            continue

        check_is_valid, check_class, load_failure = get_valid_check_class(check_name, check_path)
        if not check_is_valid:
            continue

        if manifest_path:
            validated = validate_sdk_check(manifest_path)
            if not validated:
                log.warn("The SDK check (%s) was designed for a different agent core "
                         "or couldnt be validated - behavior is undefined" % check_name)

        load_success, load_failure = _initialize_check(
            check_config, check_name, check_class, agentConfig, manifest_path
        )

        _update_python_path(check_config)

        log.debug('Loaded %s' % check_path)
        break  # we successfully initialized this check

    return load_success, load_failure


def load_check_directory(agentConfig, hostname):
    from checks import AGENT_METRICS_CHECK_NAME

    initialized_checks = {}
    init_failed_checks = {}
    agentConfig['checksd_hostname'] = hostname

    checks_places = get_checks_places(agentConfig)

    for config_path in _file_configs_paths(agentConfig):
        # '/etc/dd-agent/checks.d/my_check.py' -> 'my_check'
        check_name = _conf_path_to_check_name(config_path)

        conf_is_valid, check_config, invalid_check = _load_file_config(config_path, check_name, agentConfig)
        init_failed_checks.update(invalid_check)
        if not conf_is_valid:
            continue

        # load the check
        load_success, load_failure = load_check_from_places(check_config, check_name, checks_places, agentConfig)

        initialized_checks.update(load_success)
        init_failed_checks.update(load_failure)

    #init_failed_checks.update(deprecated_checks)
    log.info('initialized checks.d checks: %s' % [k for k in initialized_checks.keys() if k != AGENT_METRICS_CHECK_NAME])
    log.info('initialization failed checks.d checks: %s' % init_failed_checks.keys())

    return {'initialized_checks': initialized_checks.values(),
            'init_failed_checks': init_failed_checks}

# logging

def get_log_date_format():
    return "%Y-%m-%d %H:%M:%S %Z"


def get_log_format(logger_name):
    return '%(asctime)s | %(levelname)s | %(name)s(%(filename)s:%(lineno)s) | %(message)s'


def get_syslog_format(logger_name):
    return 'dd.%s[%%(process)d]: %%(levelname)s (%%(filename)s:%%(lineno)s): %%(message)s' % logger_name


def get_logging_config(cfg_path=None):
    logging_config = {
        'log_level': None
    }
    
    logging_config['collector_log_file'] = './log/collector.log'

    config_path = get_config_path(cfg_path)
    config = ConfigParser.ConfigParser()
    config.readfp(skip_leading_wsp(open(config_path)))

    for option in logging_config:
        if config.has_option('Main', option):
            logging_config[option] = config.get('Main', option)

    levels = {
        'CRITICAL': logging.CRITICAL,
        'DEBUG': logging.DEBUG,
        'ERROR': logging.ERROR,
        'FATAL': logging.FATAL,
        'INFO': logging.INFO,
        'WARN': logging.WARN,
        'WARNING': logging.WARNING,
    }
    if config.has_option('Main', 'log_level'):
        logging_config['log_level'] = levels.get(config.get('Main', 'log_level'))

    if config.has_option('Main', 'disable_file_logging'):
        logging_config['disable_file_logging'] = config.get('Main', 'disable_file_logging').strip().lower() in ['yes', 'true', 1]
    else:
        logging_config['disable_file_logging'] = False

    return logging_config


def initialize_logging(logger_name):
    try:
        logging_config = get_logging_config()

        logging.basicConfig(
            format=get_log_format(logger_name),
            level=logging_config['log_level'] or logging.INFO,
        )

        log_file = logging_config.get('%s_log_file' % logger_name)
        if log_file is not None and not logging_config['disable_file_logging']:
            # make sure the log directory is writeable
            # NOTE: the entire directory needs to be writable so that rotation works
            if os.access(os.path.dirname(log_file), os.R_OK | os.W_OK):
                file_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=LOGGING_MAX_BYTES, backupCount=1)
                formatter = logging.Formatter(get_log_format(logger_name), get_log_date_format())
                file_handler.setFormatter(formatter)

                root_log = logging.getLogger()
                root_log.addHandler(file_handler)
            else:
                sys.stderr.write("Log file is unwritable: '%s'\n" % log_file)

    except Exception as e:
        sys.stderr.write("Couldn't initialize logging: %s\n" % str(e))
        traceback.print_exc()

        # if config fails entirely, enable basic stdout logging as a fallback
        logging.basicConfig(
            format=get_log_format(logger_name),
            level=logging.INFO,
        )

    # re-get the log after logging is initialized
    global log
    log = logging.getLogger(__name__)

def load_attrid_config(cfg_path=None):
    id_map = {}
    id_with_ip = {}
    id_with_ratio = {}
    config = ConfigParser.ConfigParser()
    config.readfp(skip_leading_wsp(open(cfg_path)))
    
    ip_pattern = re.compile(r'^(\d+\.){3}\d+$')
    num_pattern = re.compile(r'^[\d\.]+$')

    attr_items = config.items('id_map');
    for item in attr_items:
        val = item[1].split(',')
        id_map[val[0].strip()] = item[0].strip()
        if len(val) >= 2:
            match = num_pattern.match(val[1])
         #   print item[0].strip(),"->",val[0].strip(),"->",val[1].strip()
            if match:
                id_with_ratio[item[0].strip()] = float(val[1].strip())
          #      print "match ratio:",val[1].strip()
            if len(val) > 2:
                print item[0].strip(),"->",val[0].strip(),"->",val[1].strip(),"->",val[2].strip()
                match = ip_pattern.match(val[2])
                if match:
           #         print "match other ip:",val[2].strip()
                    id_with_ip[item[0].strip()] = val[2].strip()
    return id_map,id_with_ratio,id_with_ip

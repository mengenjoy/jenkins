#!/usr/local/dcos_agent/py27/bin/python

"""
need to install simplejson,yaml,ntp,pymysql(if need mysql),redis(if need redis)
"""
# stdlib
import collections
import locale
import logging
import pprint
import socket
import sys
import time
import re
import os

from config import load_check_directory

# 3p
try:
    import psutil
except ImportError:
    psutil = None

import simplejson as json

# project
from util import Timer
from config import initialize_logging,load_attrid_config

initialize_logging('collector')

log = logging.getLogger(__name__)

FLUSH_LOGGING_PERIOD = 10
FLUSH_LOGGING_INITIAL = 5

COLLECT_INTERVAL = 60	#seconds
RELOAD_CHESK_INTERVAL = 60 #(RELOAD_CHESK_INTERVAL * COLLECT_INTERVAL)seconds

class Collector(object):

    def __init__(self):
        # agent config is used during checks, system_stats can be accessed through the config
        socket.setdefaulttimeout(15)
        self.initialized_checks_d = []
        self.init_failed_checks_d = {}
        self.attr_map,self.id_with_ratio,self.id_with_ip = load_attrid_config('../../etc/id.mapping')

    def run(self, agentConfig):
        hostname=''
		
        timer = Timer()
        log.debug("Starting collection run")
			
        self.run_counter = 0
        while True:
            checksd = load_check_directory(agentConfig, hostname)
            log.debug("Found {num_checks} checks".format(num_checks=len(checksd['initialized_checks'])))

            if checksd:
                self.initialized_checks_d = checksd['initialized_checks']  # is a list of AgentCheck instances
                self.init_failed_checks_d = checksd['init_failed_checks']  # is of type {check_name: {error, traceback}}

            start = time.time()
            if not self.initialized_checks_d:
                log.info("Not found checks valid, please check for it")

            # checks.d checks
            for check in self.initialized_checks_d:
                log.info("Running check %s", check.name)
                instance_statuses = []
                check_start_time = time.time()

                try:
                    # Run the check.
                    instance_statuses = check.run()

                    # Collect the metrics.    
                    current_check_metrics = check.get_metrics()
                    parse_result(current_check_metrics, self.attr_map, self.id_with_ratio, self.id_with_ip)
				
                    log.info("check result for %s: \n\t%s" %(check.name,current_check_metrics))

                except Exception:
                    log.exception("Error running check %s" % check.name)

                check_run_time = time.time() - check_start_time
                log.debug("Check %s ran in %.2f s" % (check.name, check_run_time))

            
            collect_duration = timer.step()
            collect_duration = collect_duration - (0 if collect_duration <= COLLECT_INTERVAL else COLLECT_INTERVAL)
            self.run_counter = self.run_counter + 1;
            log.info("Finished run #%d. Collection time: %ss" % (self.run_counter, round(collect_duration, 2)))
            
            if self.run_counter > RELOAD_CHESK_INTERVAL:
                log.debug("Reload checks....")
                tmp_checksd = load_check_directory(agentConfig, hostname)
		
                checksd.clear()
                checksd['init_failed_checks'] = tmp_checksd['init_failed_checks']
                checksd['initialized_checks'] = []
                
                for new_check in tmp_checksd['initialized_checks']:
                    for check in self.initialized_checks_d:
                        if new_check.name == check.name:
                            new_check.aggregator = check.aggregator
                            break
                    checksd['initialized_checks'].append(new_check)
                        
                if checksd:
                    self.initialized_checks_d = checksd['initialized_checks']  # is a list of AgentCheck instances
                    self.init_failed_checks_d = checksd['init_failed_checks']  # is of type {check_name: {error, traceback}}		
					
                log.debug("Reload done, found {num_checks} checks".format(num_checks=len(self.initialized_checks_d)))

                self.run_counter = 0
			
            #time.sleep(COLLECT_INTERVAL if self.run_counter != 0 else (COLLECT_INTERVAL - timer.step() + collect_duration))	#collect interval
            sleep_time = COLLECT_INTERVAL - time.time() + start
            time.sleep(sleep_time)
			
        return {}

    @staticmethod

    def _report(self, metrics):
        return []

def parse_result(result, attr_map, id_with_ratio, id_with_ip):
    id_val = {}
    if result:
        for item in result:
            if item and isinstance(item, tuple) and len(item) >= 3:
                key = item[0]
                value = item[2]
                attr_id = -1
                if attr_map.has_key(key):
                    attr_id = attr_map[key]
                if attr_id != -1:
                    if id_with_ratio.has_key(attr_id):
                        value = value * id_with_ratio[attr_id]
                    if id_val.has_key(attr_id):
                        id_val[attr_id] += value;
                    else:
                        id_val[attr_id] = value;
        cmd_basic = 'cd /usr/local/dcos_agent/scripts;./dcos_custom_report 0'
        #cmd_basic = 'cd /usr/local/dcos_agent/scripts;./dcos_custom_report 2'
        count = 0
        cmd = cmd_basic
        for key,value in id_val.items():
            count += 1
            cmd = '%s %s %d' % (cmd, key, value)
            if count > 0:
                os.system(cmd)
                cmd = cmd_basic
                count = 0
        if count > 0:
            os.system(cmd)
		
def main():

    # Initialize the checks
    agentConfig={}
    agentConfig["additional_checksd"] = '/usr/local/dcos/plugins/ddagent/etc/checks.d/'
	
    # Initialize the Collector
    collector = Collector()
	
    # Run the checks
    collector.run(agentConfig)
	
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except StandardError:
        # Try our best to log the error.
        try:
            log.exception("Uncaught error running the Agent")
        except Exception:
            pass
        raise

#!../../py27/bin/python
# -*- coding: utf-8 -*-

import sys, os, subprocess

def subprocess_cmd(command):
    process = subprocess.Popen(command,stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    return proc_stdout

id_map = {
    'jvm.thread_count':20001068,
    'jvm.non_heap_memory_max': 20001069,
    'jvm.non_heap_memory_init': 20001070,
    'jvm.non_heap_memory_committed': 20001071,
    'jvm.non_heap_memory': 20001072,
    'jvm.heap_memory_max': 20001073,
    'jvm.heap_memory_init': 20001074,
    'jvm.heap_memory_committed': 20001075,
    'jvm.heap_memory': 20001076,
    'jvm.gc.parnew.time': 20001077,
    'jvm.gc.cms.count': 20001078,
    'tomcat.threads.max': 20001079,
    'tomcat.threads.count': 20001080,
    'tomcat.threads.busy': 20001081,
    'tomcat.request_count': 20001082,
    'tomcat.processing_time': 20001083,
    'tomcat.max_time': 20001084,
    'tomcat.error_count': 20001085,
    'tomcat.bytes_sent': 20001086,
    'tomcat.bytes_rcvd': 20001087,
}

if len(sys.argv) != 5:
    #print 'wrong args!'
    sys.exit()

#print sys.argv

type = sys.argv[1]
name = sys.argv[2]
value = sys.argv[3]
tag = sys.argv[4]

if name not in id_map:
    #print 'no key avalaible'
    sys.exit()

id = id_map[name]
value = int(float(value))
if name.find('memory') != -1:
    #print 'convert value'
    value /= 1024

#print 'report ', id, value

dir_path = os.path.dirname(os.path.realpath(__file__))
report_scripts_path = dir_path + '/../../scripts/'

res = subprocess_cmd('cd '+report_scripts_path+';./dcos_custom_report 0 %s %s' % (str(id), str(value)))
#print res



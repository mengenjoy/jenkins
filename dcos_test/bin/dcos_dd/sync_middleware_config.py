#!/data/zhiyun/admin/py27/bin/python
# -*- coding: utf-8 -*-
"""
此脚本用于监控机器上monitor_file_dir目录下的文件是否与服务器一致。
ip获取逻辑：获取reporter中指定的网卡对应的ip。
上报本地文件的md5，获取需要更新或删除的文件，来更新或删除本地文件
"""
import base64
import datetime
import glob
import fcntl
import hashlib
import json
import logging
import logging.handlers
import os
import random
import socket
import struct
import time
import urllib2
import sys

monitor_file_dir = '/usr/local/dcos_agent/bin/dcos_dd/conf.d' # 监控的配置文件所在的目录
reporter = '/usr/local/dcos_agent/etc/reporter.conf' # reporter.conf位置
report_host = 'api.zhiyun.qcloud.com' # 上报host
report_url = 'http://{ip}/cd/monitor/report' # 上报url
log_file = '/data/log/zhiyun/monitor.log' # 日志文件


class Monitor(object):
    def __init__(self):
        self.logger = self.create_logger(log_file)
        self.report_url = ''
        """
        从reporter获取ip初始化report_url
        :return:
        """
        flag = False
        if os.path.isfile(reporter):
            with open(reporter, 'r') as f:
                for line in f.readlines():
                    if line.startswith('MIDDLEWARE_MONITOR_SERVER_IP'):
                        tmp = line.split(' ')
                        if len(tmp) > 1:
                            self.report_url = report_url.format(ip=tmp[1])
                            flag = True
        if not flag:
            self.logger.error('reporter no MIDDLEWARE_MONITOR_SERVER_IP')
            sys.exit(1)

    def create_logger(self, log_file, log_name=None, level=logging.INFO, console=False):
        """
        初始化一个logger
        :param log_name:
        :param level:
        :param console:
        :return:
        """
        if log_name is None:
            log_name = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f') + str(random.randint(0, 1e10))
        logger = logging.getLogger(log_name)
        logger.setLevel(level)
        formatter = logging.Formatter(
            '[%(asctime)-15s], function[%(funcName)s], line[%(lineno)d], [%(levelname)s]: %(message)s')
        if console:
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        try:
            handler = logging.handlers.TimedRotatingFileHandler(log_file, when='D', backupCount=30)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        except Exception, e:
            logger.warn('log file init failed:%s', e)
        return logger

    def _get_eth_name(self):
        """
        从reporter获取当前机器ip对应的网卡
        :return:
        """
        if os.path.isfile(reporter):
            with open(reporter, 'r') as f:
                for line in f.readlines():
                    if line.startswith('SPEC_NIC'):
                        tmp = line.split(' ')
                        if len(tmp) > 1:
                            return tmp[1].strip()
        self.logger.warning('reporter no SPEC_NIC')
        return 'eth1'

    def _get_ip_address(self, ifname):
        """通过网卡获取ip
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            return socket.inet_ntoa(fcntl.ioctl(
                s.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack('256s', ifname[:15])
            )[20:24])
        except Exception, e:
            self.logger.error(e)
            sys.exit(1)

    def _get_ip_address_from_pkg(self):
	"""	
	从pkg获取cmdb设置的内网ip
	"""
	pkg_ip_txt = "/data/zhiyun/ip.txt"
	if os.path.isfile(pkg_ip_txt):
	    with open(pkg_ip_txt, 'r') as f:
		for line in f.readlines():
		    return line.strip('\n')


    def get_file_list_md5(self):
        """
        获取当前机器上监控目录所有文件
        :return:
        """
        file_list = glob.glob('{0}/*'.format(monitor_file_dir))
        result = {}
        for file in file_list:
            file_name = os.path.basename(file)
            result[file_name] = ''
            if os.path.isfile(file):
                with open(file) as f:
                    result[file_name] = hashlib.md5(base64.b64encode(f.read())).hexdigest()
        return result

    def monitor(self):
        self.logger.info('monitor')
	pkg_ip = self._get_ip_address_from_pkg()
        post_data = {
            'ip': pkg_ip if pkg_ip else self._get_ip_address(self._get_eth_name()),
            'file_list_info': self.get_file_list_md5()
        }
        self.logger.info(json.dumps(post_data))
        req = urllib2.Request(
            url=self.report_url,
            data=json.dumps(post_data),
            headers={
                'HOST': report_host,
                'Content-Type': 'application/json;charset=utf-8'
            }
        )
        ori_res = urllib2.urlopen(req).read()
        self.logger.info(ori_res)
        res = json.loads(ori_res)
        if res.get('code', '') == 0:
            data = res.get('data', [])
            if type(data) == dict:
                for file, info in data.items():
                    abs_file = os.path.join(monitor_file_dir, file)
                    status = info[0]
                    content = info[1] if len(info) > 1 else ''
                    if status == 'valid':
                        with open(abs_file, 'w') as f:
                            f.write(base64.b64decode(content))
                    else:
                        if os.path.isfile(abs_file):
                            os.remove(abs_file)
        else:
            self.logger.error('report return code is not 0:' + ori_res)


if __name__ == '__main__':
    time.sleep(random.random())
    Monitor().monitor()

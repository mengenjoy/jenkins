#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import atexit
import signal
import time
import datetime
import commands
import copy

# 网卡特性ID配置说明：
#   outflow: 出流量(Kb/s)
#   inflow: 入流量(Kb/s)
#   outpkg: 出包量
#   inpkg: 入包量
#   r_errs: Receive错误数
#   t_errs: Transmit错误数
#   r_drops: Receive丢包数
#   t_drops: Transmit丢包数

NET_REPORT_CONF = {
    "bond0": {
        "outflow": 20005000,
        "inflow": 20005001,
        "outpkg": 20005002,
        "inpkg": 20005003,
        "r_errs": 20005004,
        "t_errs": 20005005,
        "r_drops": 20005006,
        "t_drops": 20005007,
    },
    "bond1": {
        "outflow": 20005008,
        "inflow": 20005009,
        "outpkg": 20005010,
        "inpkg": 20005011,
        "r_errs": 20005012,
        "t_errs": 20005013,
        "r_drops": 20005014,
        "t_drops": 20005015,
    },
}

############################################################
# 脚本名与脚本所在目录
BASE_FILE = os.path.split(os.path.realpath(sys.argv[0]))[1].split('.')[0]
BASE_PATH = os.path.split(os.path.realpath(sys.argv[0]))[0]


def get_current_datetime():
    '''获取当前系统时间'''
    now = datetime.datetime.now()
    return '[%s]' % now.strftime("%Y-%m-%d %H:%M:%S")


class Daemon(object):
    """守护进程基类"""

    def __init__(self, pidfile, stdin='/dev/null',
                 stdout='/dev/null', stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self):
        # 第一次fork
        self.fork()

        # 分离启动进程的环境变量,设置自己的环境变量
        self.dettach_env()

        # 第二次fork
        self.fork()

        # flush标准文件描述符
        sys.stdout.flush()
        sys.stderr.flush()

        self.attach_stream('stdin', mode='r')
        self.attach_stream('stdout', mode='a+')
        self.attach_stream('stderr', mode='a+')

        # 写pidfile
        self.create_pidfile()

    def attach_stream(self, name, mode):
        """重定向输出"""
        stream = open(getattr(self, name), mode)
        os.dup2(stream.fileno(), getattr(sys, name).fileno())

    def dettach_env(self):
        os.chdir("/")
        os.setsid()
        os.umask(0)

    def fork(self):
        """fork子进程"""
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            sys.stderr.write("Fork failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

    def create_pidfile(self):
        atexit.register(self.delpid)
        pid = str(os.getpid())
        open(self.pidfile, 'w+').write("%s\n" % pid)

    def delpid(self):
        """进程停止时删除pidfile文件"""
        os.remove(self.pidfile)

    def start(self):
        """启动守护进程"""
        pid = self.get_pid()

        if pid:
            message = "pidfile %s already exist. Daemon already running?\n"
            sys.stderr.write(message % self.pidfile)
            sys.exit(1)

        self.daemonize()
        self.run()

    def get_pid(self):
        """从pidfile文件中读取进程ID"""
        try:
            pf = open(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except (IOError, TypeError):
            pid = None
        return pid

    def stop(self, silent=False):
        """停止守护进程"""
        # 从pidfile中获取PID
        pid = self.get_pid()

        if not pid:
            if not silent:
                message = "pidfile %s does not exist. Daemon not running?\n"
                sys.stderr.write(message % self.pidfile)
            return

        # 使用signal杀掉进程
        try:
            while True:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
        except OSError as err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                sys.stdout.write(str(err))
                sys.exit(1)

    def restart(self):
        """重启守护进程"""
        self.stop(silent=True)
        self.start()

    def run(self):
        """继承Daemon基类，并重写run方法"""
        raise NotImplementedError


# 首次运行
first_running = True
# 用于保存上次的值
last_value = None


class MyDaemon(Daemon):
    def run(self):
        print get_current_datetime() + " Process start..."
        while True:
            global last_value
            global first_running
            # 用于保存当前的值
            current_value = copy.deepcopy(NET_REPORT_CONF)
            for interface in NET_REPORT_CONF:
                (status, output) = commands.getstatusoutput('cat /proc/net/dev | grep %s | sed -e \'s/\(.*\)\:\(.*\)/\\2/g\'' % interface)
                if len(output) <= 0:
                    print get_current_datetime() + " No data by 'cat /proc/net/dev | grep %s'" % interface
                    continue
                result = output.split()

                current_value[interface]["inflow"] = int(result[0])
                current_value[interface]["inpkg"] = int(result[1])
                current_value[interface]["r_errs"] = int(result[2])
                current_value[interface]["r_drops"] = int(result[3])

                current_value[interface]["outflow"] = int(result[8])
                current_value[interface]["outpkg"] = int(result[9])
                current_value[interface]["t_errs"] = int(result[10])
                current_value[interface]["t_drops"] = int(result[11])

                if not first_running:
                    (status, output) = commands.getstatusoutput(
                        'cd /usr/local/dcos_agent/scripts && ./dcos_custom_report 0 %s %s' % (NET_REPORT_CONF[interface]["outflow"],
                                                                                              (current_value[interface]["outflow"] - last_value[interface]["outflow"])*8/61440))
                    print get_current_datetime(), output
                    (status, output) = commands.getstatusoutput(
                        'cd /usr/local/dcos_agent/scripts && ./dcos_custom_report 0 %s %s' % (NET_REPORT_CONF[interface]["inflow"],
                                                                                              (current_value[interface]["inflow"] - last_value[interface]["inflow"])*8/61440))
                    print get_current_datetime(), output
                    (status, output) = commands.getstatusoutput(
                        'cd /usr/local/dcos_agent/scripts && ./dcos_custom_report 0 %s %s' % (NET_REPORT_CONF[interface]["outpkg"],
                                                                                              (current_value[interface]["outpkg"] - last_value[interface]["outpkg"])/60))
                    print get_current_datetime(), output
                    (status, output) = commands.getstatusoutput(
                        'cd /usr/local/dcos_agent/scripts && ./dcos_custom_report 0 %s %s' % (NET_REPORT_CONF[interface]["inpkg"],
                                                                                              (current_value[interface]["inpkg"] - last_value[interface]["inpkg"])/60))
                    print get_current_datetime(), output
                    (status, output) = commands.getstatusoutput(
                        'cd /usr/local/dcos_agent/scripts && ./dcos_custom_report 0 %s %s' % (NET_REPORT_CONF[interface]["r_errs"],
                                                                                              current_value[interface]["r_errs"] - last_value[interface]["r_errs"]))
                    print get_current_datetime(), output
                    (status, output) = commands.getstatusoutput(
                        'cd /usr/local/dcos_agent/scripts && ./dcos_custom_report 0 %s %s' % (NET_REPORT_CONF[interface]["t_errs"],
                                                                                              current_value[interface]["t_errs"] - last_value[interface]["t_errs"]))
                    print get_current_datetime(), output
                    (status, output) = commands.getstatusoutput(
                        'cd /usr/local/dcos_agent/scripts && ./dcos_custom_report 0 %s %s' % (NET_REPORT_CONF[interface]["r_drops"],
                                                                                              current_value[interface]["r_drops"] - last_value[interface]["r_drops"]))
                    print get_current_datetime(), output
                    (status, output) = commands.getstatusoutput(
                        'cd /usr/local/dcos_agent/scripts && ./dcos_custom_report 0 %s %s' % (NET_REPORT_CONF[interface]["t_drops"],
                                                                                              current_value[interface]["t_drops"] - last_value[interface]["t_drops"]))
                    print get_current_datetime(), output

            if first_running:
                last_value = current_value
                first_running = False
            else:
                last_value = current_value
            time.sleep(60)


def ansi(color, msg):
    return "\x1b[%sm%s\x1b[m" % (color, msg)


def parse_args():
    '''解析命令行参数
    '''
    if len(sys.argv) > 2:
        print ansi('31', u"Error: 命令输入错误")
    elif len(sys.argv) > 1:
        cmd = sys.argv[1]
    else:
        cmd = "help"
    return cmd


def main():
    usage = '''
    Usage: python %s [CMD]
        
        start      - start the daemon process
        stop       - stop the daemon process
        restart    - restart the daemon process
        status     - show the status of the daemon process
        help       - show the help message
    ''' % sys.argv[0]

    command = parse_args()
    daemon = MyDaemon(pidfile=BASE_PATH + "/" + BASE_FILE + ".pid",
                      stdout=BASE_PATH + "/" + BASE_FILE + ".log",
                      stderr=BASE_PATH + "/" + BASE_FILE + ".err")
    if command == 'start':
        print("Starting daemon")
        daemon.start()
        pid = daemon.get_pid()

        if not pid:
            print("Unable run daemon")
        else:
            print("Daemon is running [PID=%d]" % pid)

    elif command == 'stop':
        print("Stoping daemon")
        daemon.stop()

    elif command == 'restart':
        print("Restarting daemon")
        daemon.restart()

    elif command == 'status':
        print("Viewing daemon status")
        pid = daemon.get_pid()

        if not pid:
            print("Daemon isn't running.")
        else:
            print("Daemon is running [PID=%d]" % pid)

    elif command == 'help':
        print usage

    else:
        print ansi('31', u"Error: 命令输入错误\n")
        print usage

    sys.exit(0)


if __name__ == '__main__':
    main()

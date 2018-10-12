#!/bin/sh
#You Can set the program name and config file name below:
collect_progname='dcos_agent_collect'
report_progname='dcos_agent_report'
third_progname='dcos_dd_collector.py'

stop_proc()
{
        progname=$1
        if [[ "$progname" == "" ]];then
                echo "program name is empty, please check for it"
                return 0
        fi

        pidnum=`ps -ef | grep "./$progname" | grep -v grep | wc -l`
        if [ $pidnum -lt 1 ]
        then
                echo "not found $progname"
        else
                for pid in `ps -ef | grep "./$progname" | grep -v grep | awk '{print $2}'`
                do
                        target_exe=`readlink /proc/$pid/exe | awk '{print $1}'`
                        if [ -n "$target_exe" ]
                        then
                                local_exe=`pwd`"/$progname"
                                if [ $target_exe -ef $local_exe ]
                                then
					echo "found $progname running, pid=$pid, kill it."
                                        kill -9 $pid
                                fi
                        fi
                done
        fi
}

stop_proc2()
{
        progname=$1
        if [[ "$progname" == "" ]];then
                echo "program name is empty, please check for it"
                return 0
        fi

        pidnum=`ps -ef | grep "./$progname" | grep -v grep | wc -l`
        if [ $pidnum -lt 1 ]
        then
                echo "not found $progname"
        else
                for pid in `ps -ef | grep "./$progname" | grep -v grep | awk '{print $2}'`
                do
                        target_exe=`readlink /proc/$pid/cwd | awk '{print $1}'`
                        if [ -n "$target_exe" ]
                        then
                                local_exe=`pwd`
                                if [ $target_exe -ef $local_exe ]
                                then
                    echo "found $progname running, pid=$pid, kill it."
                                        kill -9 $pid
                                fi
                        fi
                done
        fi
}

stop_proc3()
{
    PID=`pgrep -f ".*org\.datadog\.jmxfetch\.App.*"`
    if [[ "" !=  "$PID" ]]; then
      echo "killing $PID"
      kill -9 $PID
    fi
}

if [ $# != 1 ]
then
	echo -e "USAGE: $0 option [ all | collect | report | third ]"
	exit 1;
fi

if [ $1 = "all" ]
then
	#check collector
	stop_proc "$collect_progname"
	#check reporter
	stop_proc "$report_progname"
    #check third
    cd dcos_dd
    stop_proc2 "$third_progname"
    #check tomcat
    stop_proc3
	exit 0
fi

if [ $1 = "collect" ]
then
	stop_proc "$collect_progname"
	exit 0
fi

if [ $1 = "report" ]
then
	stop_proc "$report_progname"
    exit 0
fi

if [ $1 = "third" ]
then
    cd dcos_dd
	stop_proc2 "$third_progname"
    exit 0
fi
echo "command invalid:" $1


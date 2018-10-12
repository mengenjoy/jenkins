#!/bin/sh
#You Can set the program name and config file name below:
collect_progname='dcos_agent_collect'
report_progname='dcos_agent_report'
third_progname='dcos_dd_collector.py'

start_proc()
{
	progname=$1
	if [[ "$progname" == "" ]];then
		echo "program name is empty, please check for it"
		return 0
	fi
    label=$2
    if [[ "$label" == "" ]];then
        label="0"
    fi
	pid_tag=0
    pidnum=`ps -ef | grep "./$progname" | grep -v grep | wc -l`
    if [ $pidnum -lt 1 ]
    then
        if [[ "$label" == 1 ]]
        then
            ./$progname &
        else
            ./$progname
        fi
		pidnum=`ps -ef | grep "./$progname" | grep -v grep | wc -l`
        if [ $pidnum -gt 0 ];then
            echo "$progname start success, num of pid:$pidnum"
        else
            echo "$progname start failed, please check for it."
        fi
    else
        for pid in `ps -ef | grep "./$progname" | grep -v grep | awk '{print $2}'`
        do
            target_exe=`readlink /proc/$pid/exe | awk '{print $1}'`
            if [ -n "$target_exe" ]
            then
                local_exe=`pwd`"/$progname"
                if [ $target_exe -ef $local_exe ]
                then
                    echo "$progname already started, ignore it."
                    pid_tag=1
                fi
            fi
        done
        if [[ "$pid_tag" == "0" ]];then
            if [[ "$label" == 1 ]]
            then
                ./$progname &
            else
                ./$progname
            fi
	        pidnum=`ps -ef | grep "./$progname" | grep -v grep | wc -l`
		    if [ $pidnum -gt 0 ];then
                echo "$progname start success, num of pid:$pidnum"
            else
                echo "$progname start failed, please check for it."
            fi
        fi
    fi
}

start_proc2()
{
    progname=$1
    if [[ "$progname" == "" ]];then
        echo "program name is empty, please check for it"
        return 0
    fi
    label=$2
    if [[ "$label" == "" ]];then
        label="0"
    fi
    pid_tag=0
    pidnum=`ps -ef | grep "./$progname" | grep -v grep | wc -l`
    if [ $pidnum -lt 1 ]
    then
        if [[ "$label" == 1 ]]
        then
            ./$progname &
        else
            ./$progname
        fi
        pidnum=`ps -ef | grep "./$progname" | grep -v grep | wc -l`
        if [ $pidnum -gt 0 ];then
            echo "$progname start success, num of pid:$pidnum"
        else
            echo "$progname start failed, please check for it."
        fi
    else
        for pid in `ps -ef | grep "./$progname" | grep -v grep | awk '{print $2}'`
        do
            target_exe=`readlink /proc/$pid/cwd | awk '{print $1}'`
            if [ -n "$target_exe" ]
            then
                local_exe=`pwd`
                if [ $target_exe -ef $local_exe ]
                then
                    echo "$progname already started, ignore it."
                    pid_tag=1
                fi
            fi
        done
        if [[ "$pid_tag" == "0" ]];then
            if [[ "$label" == 1 ]]
            then
                ./$progname &
            else
                ./$progname
            fi
            pidnum=`ps -ef | grep "./$progname" | grep -v grep | wc -l`
            if [ $pidnum -gt 0 ];then
                echo "$progname start success, num of pid:$pidnum"
            else
                echo "$progname start failed, please check for it."
            fi
        fi
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
	start_proc "$collect_progname"
	#check reporter
	start_proc "$report_progname"
    #check third
    cd dcos_dd
    start_proc2 "$third_progname" 1
	exit 0
fi

if [ $1 = "collect" ]
then
	start_proc "$collect_progname"
	exit 0
fi

if [ $1 = "report" ]
then
	start_proc "$report_progname"
    exit 0
fi

if [ $1 = "third" ]
then
    cd dcos_dd
    start_proc2 "$third_progname" 1
    exit 0
fi
echo "command invalid:" $1

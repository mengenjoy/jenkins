#!/bin/sh

check_proc()
{
	progname=$1
	if [[ "$progname" == "" ]];then
		echo "program name is empty, please check for it"
		return 1
	fi
	
	pid_tag=0
        pidnum=`ps -ef | grep "./$progname" | grep -v grep | wc -l`
        if [ $pidnum -lt 1 ]
        then
		echo "$progname........................not running"
		return 1
        else
                for pid in `ps -ef | grep "./$progname" | grep -v grep | awk '{print $2}'`
                do
                        target_exe=`readlink /proc/$pid/exe | awk '{print $1}'`
                        if [ -n "$target_exe" ]
                        then
                                local_exe=`pwd`"/$progname"
                                if [ $target_exe -ef $local_exe ]
                                then
                                        pid_tag=1
                                fi
                        fi
                done
                if [[ "$pid_tag" == "0" ]];then
			echo "$progname........................not running"
			return 1
		else
			echo "$progname........................running"
			return 0
                fi
        fi
}


cd ./bin

check_proc "dcos_agent_report"
ret=$?
check_proc "dcos_agent_collect"
tmp=$?
if [[ "0" == "$ret" ]];then
        ret=$tmp
fi
exit $ret

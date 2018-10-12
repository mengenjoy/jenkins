#!/bin/bash

Log_Path=/usr/local/dcos_agent/log/
Days=7
tar_bin=$(which tar)
find_bin=$(which find)

cd ${Log_Path} || exit 1

function Tar(){
    type tar >/dev/null 2>&1 || exit 1
    #for file in `${find_bin} . -mtime +${Days} -regextype posix-egrep -regex "\./syslog\.[0-9]{4}-[0-9]{2}-[0-9]{2}$"`;do
    for file in `${find_bin} . -mtime +${Days} -name "agent_*" -type f ! -name "*.tar.gz"`;do
        ${tar_bin} cvzf ${file}.tar.gz --remove-files ${file}
    done
}

Tar && exit 0


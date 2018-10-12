#!/bin/sh

if [ -f sc_agent.tgz ];then
	tar zxf sc_agent.tgz
fi
cd ./bin
./stop_sc_agent.sh all
./start_sc_agent.sh all

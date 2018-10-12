#!/bin/sh
COUNT=`crontab -l | grep "start_sc_agent.sh" | grep -v "grep"|wc -l`
if [ $COUNT -eq 1 ]; then
    (crontab -l 2>/dev/null | grep -Fv "start_sc_agent.sh") | crontab -
fi

SYNC_COUNT=`crontab -l | grep "sync_middleware_config.py" | grep -v "grep"|wc -l`
if [ $SYNC_COUNT -eq 1 ]; then
    (crontab -l 2>/dev/null | grep -Fv "sync_middleware_config.py") | crontab -
fi

cd /usr/local/dcos_agent/bin
./stop_sc_agent.sh all

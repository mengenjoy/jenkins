#!/bin/sh
crontab -l > /tmp/crontab.bak

COUNT=`crontab -l | grep "start_sc_agent.sh" | grep -v "grep"|wc -l`
if [ $COUNT -lt 1 ]; then
    CRONTAB_CMD="* * * * * cd /usr/local/dcos_agent/bin;./start_sc_agent.sh all 1>/dev/null 2>&1"
    (crontab -l 2>/dev/null | grep -Fv "start_sc_agent.sh"; echo "$CRONTAB_CMD") | crontab -
fi

SYNC_COUNT=`crontab -l | grep "sync_middleware_config.py" | grep -v "grep"|wc -l`
if [ $SYNC_COUNT -lt 1 ]; then
    SYNC_CRONTAB_CMD="* * * * * /data/zhiyun/admin/py27/bin/python /usr/local/dcos_agent/bin/dcos_dd/sync_middleware_config.py"
    (crontab -l 2>/dev/null | grep -Fv "sync_middleware_config.py"; echo "$SYNC_CRONTAB_CMD") | crontab -
fi

SQ_PU_REPORTER_COUNT=`crontab -l | grep "partition_utilization_reporter" | grep -v "grep"|wc -l`
if [ $SQ_PU_REPORTER_COUNT -lt 1 ]; then
    PUR_CRONTAB_CMD="* * * * * /usr/local/dcos_agent/bin/zhiyun/partition_utilization_reporter/partition_utilization_reporter -c /usr/local/dcos_agent/bin/zhiyun/partition_utilization_reporter/conf.json >> /usr/local/dcos_agent/log/agent_zy_pur.log 2>&1"
    (crontab -l 2>/dev/null | grep -Fv "partition_utilization_reporter"; echo "$PUR_CRONTAB_CMD") | crontab -
fi

cd /usr/local/dcos_agent/bin
./start_sc_agent.sh all

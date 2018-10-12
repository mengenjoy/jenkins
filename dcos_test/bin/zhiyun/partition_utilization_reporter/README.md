上汽磁盘分区使用率上报工具
==========================

上汽磁盘分区挂载点监控方法

1. 先要确认在`t_attr_info`表中插入对应挂载点的attrId

2. 修改配置。在`conf.json`中新加`path_attrid_map`的配置，设置好`collector`服务地址（注意要合法的JSON格式）

3. 运行`./partition_utilization_reporter -c conf.json`

#!/bin/bash

device="$1"
cd /usr/local/dcos_agent/tools

if [ $# -eq 2 ] 
then
    cp /usr/local/dcos_agent/caches/$2 /usr/local/dcos_agent/tools/smartinfo
else if [ $# -eq 1 ]
     then
        ./smartctl -a $device > smartinfo
        if [ $? -ne 0  ]; then
            echo "No such device"
        fi		
     fi
fi

sn=$(cat smartinfo | grep "Serial Number" | awk -F ':' '{print $2}' | awk '{print $1}')
tmp=$(cat smartinfo | grep "ment test")
tmp1=$(cat smartinfo | grep "ment test" | grep "PASSED")
tmp2=$(cat smartinfo | grep "SMART Health")
tmp3=$(cat smartinfo | grep "SMART Health" | grep "OK")

function sata_disk_check(){

if [ ${#tmp} -gt 0 ]
then	
    if [ ${#tmp1} -gt 0 ]
    then 
	    echo $device $sn "SMART check passed"
    else 
	    echo $device $sn "need be replaced(SMART Failure)"
		return
    fi  
else if [ ${#tmp2} -gt 0 ]
then 
    if [ ${#tmp3} -gt 0 ]
    then 
	    echo $device $sn "SMART check passed"
    else 
	    echo $device $sn "need be replaced(SMART Failure)"
        return
	fi   
    fi
fi


tmp5=$(cat smartinfo | grep "Device Model" | grep " ST")
tmp6=$(cat smartinfo | grep "SATA Version")
tmp7=$(cat smartinfo | grep "Rotation Rate" | grep "rpm")
tmp8=$(cat smartinfo | grep "Firmware Version" | grep "HPG0")
tmp9=$(cat smartinfo | grep "Firmware Version" | grep "4PC1HPG")
tmp10=$(cat smartinfo | grep "Firmware Version" | grep "HPG")
tmp11=$(cat smartinfo | grep "ATA Version")

if [ ${#tmp8} -gt 0 ] || [ ${#tmp9} -gt 0 ];then
    echo "HP disk FW don't support"
	return
fi

if [ ${#tmp5} -gt 0 -o ${#tmp10} -gt 0 ] && [ ${#tmp6} -gt 0 -o ${#tmp11} -gt 0 ] && [ ${#tmp7} -gt 0 ]
then 
    Pending_count=$(cat smartinfo | grep "Current_Pending_Sector"  | awk '{print $10}')
    if [ $Pending_count -eq 0 ];then
    echo $device $sn "is Healthy"
    else
	Reallocated_count=$(cat smartinfo | grep "Reallocated_Sector_Ct"  | awk '{print $10}')	
	if [ $[$Pending_count+$Reallocated_count] -lt 800 ];then
        readplba="./sg_raw -r 512 "$device" 85 09 0E 00 D5 00 01 00 A9 00 4F 00 C2 A0 B0 00"
		plbaentry=$($readplba)
	    step=85
		version=${plbaentry:8:2}
	    tag=${plbaentry:$step:2}
	    let "step += 18"
        #获取需要修复的LBA地址			
	    plba_low=${plbaentry:$step:12}
	    let "step += 12"
	    plba_high=${plbaentry:$step:6}
        let "step += 47"
	    if [ "$version" = "01" ] ;then
            tmp=${plba_low:10:2}${plba_low:7:2}${plba_low:3:2}${plba_low:0:2}
        else if [ "$version" = "02" ] ;then
            tmp=${plba_high:4:2}${plba_high:1:2}${plba_low:10:2}${plba_low:7:2}${plba_low:3:2}${plba_low:0:2}
        else
            echo "version don't match"
            return
        fi
	    fi
		#默认16进制数转换为10进制数
		LBA=$((16#$tmp))
		if [ $LBA -eq 0 ];then
			echo $device $sn $LBA "is 0 , the LBA address is failed"
			return
		fi
		echo $device $sn $LBA "need be repaired"
	else echo $device $sn "need be replaced(glist+plist > 800)"
	fi
    fi
fi

} 

sata_disk_check

	 

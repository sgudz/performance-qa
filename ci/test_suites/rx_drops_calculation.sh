#!/bin/bash 
 
display_usage() { 
        echo "This script must be run with two arguments" 
        echo -e "\nUsage:\n$0 [INTERFACE_NAME] [TEST_TIME_SECONDS]\n" 
        }
if [  $# -le 1 ] 
        then 
                display_usage
                exit 1
        fi

IFACE=$1
TIME=$2
ifconfig $IFACE > /tmp/$IFACE.data_before_test

RX_DROPPED_BEFORE=`cat /tmp/$IFACE.data_before_test | grep "RX packets" | grep -Eo "dropped:[0-9]*" | cut -d ":" -f2`
RX_TOTAL_BEFORE=`cat /tmp/$IFACE.data_before_test | grep "RX packets" | grep -Eo "packets:[0-9]*" | cut -d ":" -f2`

echo "RX_TOTAL BEFORE TEST is $RX_TOTAL_BEFORE"
echo "RX_DROPPED_BEFORE TEST is $RX_DROPPED_BEFORE"

sleep $TIME

ifconfig $IFACE > /tmp/$IFACE.data_after_test

RX_DROPPED_AFTER=`cat /tmp/$IFACE.data_after_test | grep "RX packets" | grep -Eo "dropped:[0-9]*" | cut -d ":" -f2`
RX_TOTAL_AFTER=`cat /tmp/$IFACE.data_after_test | grep "RX packets" | grep -Eo "packets:[0-9]*" | cut -d ":" -f2`

echo "RX_TOTAL AFTER TEST is $RX_TOTAL_AFTER"
echo "RX_DROPPED_AFTER TEST is $RX_DROPPED_AFTER"

let RX_DURING_TEST=$RX_TOTAL_AFTER-$RX_TOTAL_BEFORE
let RX_PER_SEC=$RX_DURING_TEST/180
echo "RX PER SEC is $RX_PER_SEC"

let DROP_DURING_TEST=$RX_DROPPED_AFTER-$RX_DROPPED_BEFORE
let PERCENTAGE=$DROP_DURING_TEST*100/$RX_DURING_TEST
echo $PERCENTAGE

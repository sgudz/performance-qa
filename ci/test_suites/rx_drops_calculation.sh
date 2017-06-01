#!/bin/bash 
 
display_usage() { 
        echo "This script must be run with two arguments" 
        echo -e "\nUsage:\n $0 [INTERFACE_NAME] [TEST_TIME_SECONDS] [RX or TX]\n" 
        }
if [  $# -le 1 ] 
        then 
                display_usage
                exit 1
        fi

IFACE=$1
TIME=$2
RX_TX=$3
ifconfig $IFACE > /tmp/$IFACE.data_before_test

DROPPED_BEFORE=`cat /tmp/$IFACE.data_before_test | grep "$RX_TX packets" | grep -Eo "dropped:[0-9]*" | cut -d ":" -f2`
TOTAL_BEFORE=`cat /tmp/$IFACE.data_before_test | grep "$RX_TX packets" | grep -Eo "packets:[0-9]*" | cut -d ":" -f2`

echo "Waiting for $TIME second to collect data"
sleep $TIME

ifconfig $IFACE > /tmp/$IFACE.data_after_test

DROPPED_AFTER=`cat /tmp/$IFACE.data_after_test | grep "$RX_TX packets" | grep -Eo "dropped:[0-9]*" | cut -d ":" -f2`
TOTAL_AFTER=`cat /tmp/$IFACE.data_after_test | grep "$RX_TX packets" | grep -Eo "packets:[0-9]*" | cut -d ":" -f2`

let DURING_TEST=$TOTAL_AFTER-$TOTAL_BEFORE
let PER_SEC=$DURING_TEST/$TIME
echo "$RX_TX packets per second: $PER_SEC pps"

let DROP_DURING_TEST=$DROPPED_AFTER-$DROPPED_BEFORE
if [ $DURING_TEST == 0 ]; then
  echo "0 packets during test"
  exit 0
fi

let PERCENTAGE=$DROP_DURING_TEST*100/$DURING_TEST
echo "Total packets recieved during test: $DURING_TEST"
echo "Total dropped packets during test: $DROP_DURING_TEST"
echo "$PERCENTAGE % dropped packets"

#!/bin/bash
#set -x
#This script should be run from the Master node in order to install and launch Shaker
#This script tests "storage" network for test between nodes. You can change network by replacing NETWORK parameter(to do).
export DATE=`date +%Y-%m-%d_%H:%M`
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TEST_STATUS_FILE=${DIR}/shaker_test_status.txt
rm ${TEST_STATUS_FILE} || true
touch ${TEST_STATUS_FILE}
echo "running" > ${TEST_STATUS_FILE}

####################### Catching scenarios #############################################
curl -s 'http://172.16.44.5/for_workarounds/shaker_scenario_for_perf_labs/nodes.yaml' > nodes.yaml
curl -s 'http://172.16.44.5/for_workarounds/shaker_scenario_for_perf_labs/VMs.yaml' > VMs.yaml

export SSH_OPTS='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=quiet'
CONTROLLER_ADMIN_IP=`fuel node | grep controller | awk -F "|" '{print $5}' | sed 's/ //g' | head -n 1`

export CONTROLLER_PUBLIC_IP=$(ssh ${CONTROLLER_ADMIN_IP} "ifconfig | grep br-ex -A 1 | grep inet | awk ' {print \$2}' | sed 's/addr://g'")
echo "Controller Public IP: $CONTROLLER_PUBLIC_IP"

################### Define 2 computes IPs for testing between nodes ####################
COMPUTE_IP_ARRAY=`fuel node | awk -F "|" '/compute/ {print $5}' | sed 's/ //g' | head -n 2`

########### Update traffic.py file to have stdev and median values in the report ########
curl -s 'https://raw.githubusercontent.com/vortex610/shaker/master/traffic.py' > traffic.py

##################################### Run Shaker on Controller ##########################
echo "Install Shaker on Controller"
REMOTE_SCRIPT=`ssh $CONTROLLER_ADMIN_IP "mktemp"`
ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP "cat > ${REMOTE_SCRIPT}" <<EOF
#set -x
source /root/openrc
SERVER_ENDPOINT=$CONTROLLER_PUBLIC_IP
printf 'deb http://ua.archive.ubuntu.com/ubuntu/ trusty universe' > /etc/apt/sources.list
apt-get update
apt-get -y --force-yes install iperf python-dev libzmq-dev python-pip && pip install pbr pyshaker

iptables -I INPUT -s 10.0.0.0/8 -j ACCEPT
iptables -I INPUT -s 172.16.0.0/16 -j ACCEPT
iptables -I INPUT -s 192.168.0.0/16 -j ACCEPT

shaker-image-builder --flavor-vcpu 8 --flavor-ram 4096 --flavor-disk 55 --debug

#Copy orig traffic.py
cp /usr/local/lib/python2.7/dist-packages/shaker/engine/aggregators/traffic.py /usr/local/lib/python2.7/dist-packages/shaker/engine/aggregators/traffic.py.orig
EOF
#Run script on remote node
ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP "bash ${REMOTE_SCRIPT}"

##################################### Copying scenarios to right directory ###############
echo "Copying required files to specific directories"
scp nodes.yaml $CONTROLLER_ADMIN_IP:/usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/
scp VMs.yaml $CONTROLLER_ADMIN_IP:/usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/
scp traffic.py $CONTROLLER_ADMIN_IP:/usr/local/lib/python2.7/dist-packages/shaker/engine/aggregators/traffic.py
##################################### Install Shaker on computes #########################
sleep 5

############################## Runing scenarios ############################################

echo "Run scenarios for VMs"
ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP "cat > ${REMOTE_SCRIPT3}" <<EOF
#set -x
source /root/openrc
SERVER_ENDPOINT=$CONTROLLER_PUBLIC_IP
SERVER_PORT=18000
shaker --server-endpoint \$SERVER_ENDPOINT:\$SERVER_PORT --scenario /usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/VMs.yaml --report VMs-$DATE.html --debug
EOF
ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP "bash ${REMOTE_SCRIPT3}"

########################## Copying reports to Fuel master node ###########################
scp $CONTROLLER_ADMIN_IP:/root/VMs-$DATE.html /root/VMs-$DATE.html
JSON_DATA=$(cat /root/VMs-$DATE.html | grep -P "var report" | sed 's/    var report = //g' | sed 's/\;$//g')
#echo "[test_json]" >> env.conf
#echo "json_data =" $JSON_DATA >> env.conf
echo $JSON_DATA > results.json

#/usr/bin/python addresult.py
echo "Done."

echo "finished" > ${TEST_STATUS_FILE}

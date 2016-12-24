#!/bin/bash
#set -x
#This script should be run from the Master node in order to install and launch Shaker
#This script tests "storage" network for test between nodes. You can change network by replacing NETWORK parameter(to do).
export BETWEEN_NODES=true
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

export CONTROLLER_PUBLIC_IP=$(ssh ${CONTROLLER_ADMIN_IP} "ifconfig br-ex | grep 'inet addr' | cut -d ':' -f2 | cut -d ' ' -f1")
echo "Controller Public IP: $CONTROLLER_PUBLIC_IP"

################### Define 2 computes IPs for testing between nodes ####################
COMPUTE_IP_ARRAY=`fuel node | awk -F "|" '/compute/ {print $5}' | sed 's/ //g' | head -n 2`
echo "Compute IPs:"
for i in ${COMPUTE_IP_ARRAY[@]};do echo $i;done

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
if $BETWEEN_NODES;then
echo "Install Shaker on Computes and launch local agents"
cnt="1"
for item in ${COMPUTE_IP_ARRAY[@]};do
	REMOTE_SCRIPT2=`ssh ${SSH_OPTS} $item "mktemp"`
	ssh ${SSH_OPTS} $item "cat > ${REMOTE_SCRIPT2}" <<EOF
#set -x
printf 'deb http://ua.archive.ubuntu.com/ubuntu/ trusty universe' > /etc/apt/sources.list
apt-get update
apt-get -y --force-yes install iperf python-dev libzmq-dev python-pip && pip install pbr pyshaker

iptables -I INPUT -s 10.0.0.0/8 -j ACCEPT
iptables -I INPUT -s 172.16.0.0/16 -j ACCEPT
iptables -I INPUT -s 192.168.0.0/16 -j ACCEPT
EOF
	ssh ${SSH_OPTS} $item "bash ${REMOTE_SCRIPT2}"
	agent_id="a-00$cnt"
	ssh ${SSH_OPTS} $item "screen -dmS shaker-agent-screen shaker-agent --server-endpoint=$CONTROLLER_ADMIN_IP:19000 --agent-id=$agent_id"
	cat ${REMOTE_SCRIPT2}

################################## Changing test files for agent and IP's roles ############

	if test $agent_id == "a-001";then
		role="master"
		ip=`ssh ${SSH_OPTS} $item ifconfig br-storage | grep 'inet addr' | cut -d ':' -f2 | cut -d ' ' -f1`
		FOR_SED="ip: $ip"
		MASTER_IP=`ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP "sed -n '11p;11q' /usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml | sed 's/    //g'"`
		ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP "sed -i 's/${MASTER_IP}/${FOR_SED}/g' /usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml"
		ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP cat /usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml | head -n 13
	else
		role="slave"
		ip=`ssh ${SSH_OPTS} $item ifconfig br-storage | grep 'inet addr' | cut -d ':' -f2 | cut -d ' ' -f1`
		FOR_SED="ip: $ip"
		SLAVE_IP=`ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP "sed -n '16p;16q' /usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml | sed 's/    //g'"`
		ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP "sed -i 's/${SLAVE_IP}/${FOR_SED}/g' /usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml"
		ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP cat /usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml | head -n 18
	fi
	echo "$agent_id launched. IP is $ip. Role is $role"

################################ If slave - launch iperf server ############################

	ssh ${SSH_OPTS} $item "screen -dmS iperf-screen iperf -s"
	cnt=$[cnt+1]
	sleep 2
done

############################## Runing scenarios ############################################

echo "Run scenarios for Nodes"
REMOTE_SCRIPT4=`ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP "mktemp"`
ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP "cat > ${REMOTE_SCRIPT4}" <<EOF
#set -x
source /root/openrc
SERVER_ENDPOINT=$CONTROLLER_PUBLIC_IP
SERVER_PORT2=19000
echo "SERVER_ENDPOINT: \$SERVER_ENDPOINT:\$SERVER_PORT"
shaker --server-endpoint \$SERVER_ENDPOINT:\$SERVER_PORT2 --scenario /usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml --report nodes-$DATE.html --debug
EOF
ssh ${SSH_OPTS} $CONTROLLER_ADMIN_IP "bash ${REMOTE_SCRIPT4}"
fi
#################### Cleaning after nodes testing ########################################
for proc in ${COMPUTE_IP_ARRAY[@]};do
	ssh ${SSH_OPTS} $proc "ps -ef | grep iperf | awk '{print \$2}' | xargs kill"
	ssh ${SSH_OPTS} $proc "ps -ef | grep shaker | awk '{print \$2}' | xargs kill"
 done

########################## Copying reports to Fuel master node ###########################
export DATE2=`date +%Y-%m-%d_%H:%M`
scp $CONTROLLER_ADMIN_IP:/root/nodes-$DATE.html /root/nodes-$DATE2.html
JSON_DATA=$(cat /root/nodes-$DATE2.html | grep -P "var report" | sed 's/    var report = //g' | sed 's/\;$//g')
#echo "[test_json]" >> env.conf
#echo "json_data =" $JSON_DATA >> env.conf
echo $JSON_DATA > results.json
MEDIAN=$(grep -Po '"median":(\d*?,|.*?[^\\]",)' results.json | cut -d " " -f2 | sed 's/\,//g' | cut -d "." -f1)
STDEV=$(grep -Po '"median":(\d*?,|.*?[^\\]",)' results.json | cut -d " " -f4 | sed 's/\,//g' | cut -d "." -f1)
echo "MEDIAN IS ${MEDIAN}"
echo "STDEV IS ${STDEV}"
export MEDIAN
export STDEV
#/usr/bin/python addresult.py
echo "Done."
echo "STARTED TEST AT $DATE, FINISHED AT $DATE2"
echo "finished" > ${TEST_STATUS_FILE}

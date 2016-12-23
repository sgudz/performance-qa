#!/bin/bash
export DATE=`date +%Y-%m-%d_%H:%M`
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TEST_STATUS_FILE=${DIR}/wally_test_status.txt
rm ${TEST_STATUS_FILE} || true
touch ${TEST_STATUS_FILE}
echo "running" > ${TEST_STATUS_FILE}

export SSH_OPTS='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=quiet'
CONTROLLER_IP=`fuel node | grep controller | awk -F "|" '{print $5}' | sed 's/ //g' | head -n 1`
REPL=$(ssh $CONTROLLER_IP "ceph osd dump | grep 'replicated size [23]' | head -n 1 | awk '{print \$6}'")
echo "Replication Factor is $REPL"
echo "repl =" $REPL >> env.cfg
### Create image wally_ubuntu if it doesnt exist
REMOTE_SCRIPT1=`ssh ${SSH_OPTS} $CONTROLLER_IP "mktemp"`
ssh ${SSH_OPTS} $CONTROLLER_IP "cat > ${REMOTE_SCRIPT1}" <<EOF
set -x
source /root/openrc
openstack keypair delete wally_vm_key
IMAGE=\$(glance image-list | awk '/wally_ubuntu/ {print \$4}')
echo \${IMAGE}
if [ -z \${IMAGE} ];then
wget --quiet "https://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img"
glance image-create --name wally_ubuntu --disk-format qcow2 --container-format bare --visibility public --file "trusty-server-cloudimg-amd64-disk1.img"
rm /root/trusty-server-cloudimg-amd64-disk1.img
fi
PROJECT_ID=\$(openstack project show admin | grep id | awk '{print \$4}')
cinder quota-update --gigabytes 2000 \$PROJECT_ID
EOF
ssh ${SSH_OPTS} $CONTROLLER_IP "bash ${REMOTE_SCRIPT1}"

### Install and launch wally
REMOTE_SCRIPT=`ssh ${SSH_OPTS} $CONTROLLER_IP "mktemp"`
ssh ${SSH_OPTS} $CONTROLLER_IP "cat > ${REMOTE_SCRIPT}" <<EOF
set -x
printf 'deb http://ua.archive.ubuntu.com/ubuntu/ trusty universe' > /etc/apt/sources.list
apt-get update
apt-get -y --force-yes install git python-pip python-dev libxft-dev libblas-dev liblapack-dev libatlas-base-dev gfortran python-numpy python-scipy python-matplotlib ipython ipython-notebook python-pandas python-sympy python-nose libblas3gf liblapack3gf libgfortran3 gfortran-4.6 gfortran libatlas3gf-base libfreetype6 libpng12-dev pkg-config swift libxml2-dev libxslt1-dev zlib1g-dev
pip install --upgrade pip
pip install paramiko pbr vcversioner pyOpenSSL texttable sshtunnel lxml pandas
git clone https://github.com/Mirantis/disk_perf_test_tool.git
cd disk_perf_test_tool/
#sed -i 's/, 15, 25, 40, 80, 120//g' wally/suits/io/ceph.cfg
#sed -i 's/ 1, 3,//g' wally/suits/io/ceph.cfg
sed -i 's/runtime=180/runtime=360/g' wally/suits/io/ceph.cfg
#sed -i 's/ramp_time=30/ramp_time=5/g' wally/suits/io/ceph.cfg
pip install -r requirements.txt
curl -s https://raw.githubusercontent.com/vortex610/mos/master/run_tests/shaker_run/plugin/test1.yaml > test1.yaml
curl -s https://raw.githubusercontent.com/vortex610/mos/master/run_tests/shaker_run/default.yaml > default.yaml
python -m wally test "Fuel 9.1 RC" test1.yaml
EOF
ssh ${SSH_OPTS} $CONTROLLER_IP "bash ${REMOTE_SCRIPT}"

scp ${SSH_OPTS} $CONTROLLER_IP:/var/wally_results/*/ceph_report.html /root/
scp ${SSH_OPTS} $CONTROLLER_IP:/var/wally_results/*/report.txt /root/wally_report_$DATE.txt
scp ${SSH_OPTS} $CONTROLLER_IP:/var/wally_results/*/log.txt /root/wally_log_$DATE.txt

python add_results_new.py
echo "Done."
echo "finished" > ${TEST_STATUS_FILE}

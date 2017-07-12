#!/bin/bash

source /root/keystonerc
vlan=${VLAN:=1815}

display_usage() { 
        echo "This script must be run with 3 arguments (Or you can use one argument \"default\" for default usage or cleaup for cleanup from VMs and ports)" 
        echo -e "Usage:\n $0 [physnet_name] [ports per VM] [same compute (true/false)]"
	echo -e " $0 default\n"
        echo -e "Example:\n $0 physnet1 2 2 false  --  for custom values"
	echo -e " $0 default  --  for default values (physnet_name=physnet1, ports_per_VM=2, same_compute=false)"
	echo -e " $0 cleanup  --  for cleanup created VMs and ports"
        }

cleanup() {
	if [ -z "`neutron port-list | grep sriov-port`" ]; then
		echo "Nothing to cleanup"
		exit 0
	fi
	vms_list=`nova list | awk '/sriov-vm/ {print $2}'`
	for vm in ${vms_list}; do nova delete $vm; done
	port_list=`neutron port-list | awk '/sriov-port/ {print $2}'`
	for port in ${port_list}; do neutron port-delete $port; done
	}

if [ "$1" == "cleanup" ]
	then
		cleanup
		echo "Done"
		exit 0

elif [ "$1" == "default" ]
	then
		echo "Using default parameters: "
		physnet_name="physnet1"
		ports_per_vm=2
		same_compute="false"

elif [  $# -ne 3 ] 
        then
                display_usage
                exit 1
		
else
		physnet_name=$1
		ports_per_vm=$2
		same_compute=$3
	fi

echo -e " Physnet name is: $physnet_name\n Ports per VM: $ports_per_vm\n VMs on same compute: $same_compute"
sleep 2


### Create network for SR-IOV if doesn't exist
if [ -z "`neutron net-list | grep sriov-net`" ]; then
	net_id=`neutron net-create --provider:physical_network=$physnet_name --provider:segmentation_id=$vlan sriov-net | awk '/ id/ {print $4}'`
	neutron subnet-create $net_id 10.250.0.0/24
else
	net_id=`neutron net-list | awk '/sriov-net/ {print $2}'`
fi
#echo $net_id


### Using custom image with pktgen (MoonGen) and dpdk built
if [ -z "`glance image-list | grep ubuntu1604pktgen`" ]; then
        wget http://mos-scale-share.mirantis.com/sgudz/ubuntu1604pktgen.qcow2
        openstack image create --disk-format qcow2 --container-format bare --public --file ubuntu1604pktgen.qcow2 ubuntu1604pktgen
fi

### Create flavor with 4 vcpu and 8G RAM with cpu_pinning and 1G hugepages if doesn't exist
if [ -z "`nova flavor-list | grep huge`" ]; then
        nova flavor-create huge4vcpu 12345 8192 140 4
        nova flavor-key 12345 set hw:cpu_policy=dedicated
        nova flavor-key 12345 set hw:mem_page_size=1048576
fi

### Create necessary number of ports depends on defined variables

first_compute=`nova  availability-zone-list | grep -oE "cmp[0-9]*" | awk 'NR==1'`
second_compute=`nova  availability-zone-list | grep -oE "cmp[0-9]*" | awk 'NR==2'`
computes_number=`nova  availability-zone-list | grep -oE "cmp[0-9]*" | wc -l`
#echo $first_compute $second_compute

arguments_first=""
arguments_second=""
for (( port=1; port<=$ports_per_vm; port++ ))
do
	if [ "$same_compute" == "false" ]; then
		port_id_first_compute[$port]=`neutron port-create --name sriov-port-$port-$first_compute $net_id --binding:vnic_type direct | awk '/ id/ {print $4}'`
		arguments_first+=" --nic port-id=${port_id_first_compute[$port]}"
		port_id_second_compute[$port]=`neutron port-create --name sriov-port-$port-$second_compute $net_id --binding:vnic_type direct | awk '/ id/ {print $4}'`
		arguments_second+=" --nic port-id=${port_id_second_compute[$port]}"
#		echo ${port_id[$port]}
	elif [ "$same_compute" == "true" ]; then
		port_id_first_vm_[$port]=`neutron port-create --name sriov-port-$port-first-vm-$first_compute $net_id --binding:vnic_type direct | awk '/ id/ {print $4}'`
		arguments_first+=" --nic port-id=${port_id_first_vm_[$port]}"
		port_id_second_vm_[$port]=`neutron port-create --name sriov-port-$port-second-vm-$first_compute $net_id --binding:vnic_type direct | awk '/ id/ {print $4}'`
		arguments_second+=" --nic port-id=${port_id_second_vm_[$port]}"
	fi
	
done

#echo $arguments_first $arguments_second



if [ "$same_compute" == "false" ]; then
	nova boot --flavor huge4vcpu --image ubuntu1604pktgen --availability-zone nova:$first_compute:$first_compute $arguments_first sriov-vm-$first_compute
	nova boot --flavor huge4vcpu --image ubuntu1604pktgen --availability-zone nova:$second_compute:$second_compute $arguments_second sriov-vm-$second_compute
else
	nova boot --flavor huge4vcpu --image ubuntu1604pktgen --availability-zone nova:$first_compute:$first_compute $arguments_first sriov-vm-1-$first_compute
	nova boot --flavor huge4vcpu --image ubuntu1604pktgen --availability-zone nova:$first_compute:$first_compute $arguments_second sriov-vm-2-$first_compute
#nova boot --flavor huge4vcpu --image ubuntu1604pktgen --availability-zone nova:cmp001:cmp001 --nic port-id=$port_id_cmp001 --nic port-id=$port_id_cmp002 sriov-vm-cmp001
fi

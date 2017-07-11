#!/bin/bash

display_usage() {
        echo "This script must be run with 4 arguments (Or you can use one argument \"default\" for default usage)"
        echo -e "Default values are: physnet_name=physnet1, ports_per_VM=2, VMs_count=2, same_compute=false\n"
        echo -e "Usage:\n $0 [physnet_name] [ports per VM]  [VMs count] [same compute (true/false)]"
        echo -e " $0 default\n"
        echo -e "Example:\n $0 physnet1 2 2 false  --  for custom values"
        echo -e " $0 default  --  for default values"
        }

vlan=1815

if [  $# -ne 4 ] && [ "$1" != "default" ]
        then
                display_usage
                exit 1
        elif [ "$1" == "default" ]
        then
                echo "Using default parameters: "
                physnet_name="physnet1"
                ports_per_vm=2
                vms=2
                same_compute="false"
        else
                physnet_name=$1
                ports_per_vm=$2
                vms=$3
                same_compute=$4
        fi

echo -e "Physnet name is: $physnet_name, Ports per VM: $ports_per_vm, Total VMs: $vms, VMs on same compute: $same_compute"

source /root/keystonerc

### Create network for SR-IOV if doesn't exist
if [ -z "`neutron net-list | grep sriov-net`" ]; then
        net_id=`neutron net-create --provider:physical_network=$physnet_name --provider:segmentation_id=$vlan sriov-net | awk '/ id/ {print $4}'`
        neutron subnet-create $net_id 10.250.0.0/24
else
        net_id=`neutron net-list | awk '/sriov-net/ {print $2}'`
fi
echo $net_id

### Create necessary number of ports depends on defined variables

for (( port=1; port<=$ports_per_vm; port++ ))
do
        if [ "$same_compute" == "false" ]; then
                echo "Creating VMs on different computes"
                computes=`nova  availability-zone-list | grep -oE "cmp[0-9]*"`
                computes_number=`nova  availability-zone-list | grep -oE "cmp[0-9]*" | wc -l`
                port_id[$port]=`neutron port-create --name sriov-port-$port-cmp001 $net_id --binding:vnic_type direct | awk '/ id/ {print $4}'`
                echo ${port_id[$port]}
        elif [ "$same_compute" == "true" ]; then
                echo "Creating VMs on same compute"
        fi
done
#port_id_cmp001=`neutron port-create --name sriov-port-1-cmp001 $net_id --binding:vnic_type direct | awk '/ id/ {print $4}'`
#port_id_cmp002=`neutron port-create --name sriov-port-1-cmp002 $net_id --binding:vnic_type direct | awk '/ id/ {print $4}'`
#echo $port_id_cmp001
#echo $port_id_cmp002


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


#nova boot --flavor huge4vcpu --image ubuntu1604pktgen --availability-zone nova:cmp001:cmp001 --nic port-id=$port_id_cmp001 --nic port-id=$port_id_cmp002 sriov-vm-cmp001

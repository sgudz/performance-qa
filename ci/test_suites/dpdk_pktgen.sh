apt-get install libpcap-dev make cmake git

wget http://fast.dpdk.org/rel/dpdk-16.11.1.tar.xz
wget http://dpdk.org/browse/apps/pktgen-dpdk/snapshot/pktgen-dpdk-pktgen-3.1.2.tar.gz
tar -xf dpdk-16.11.1.tar.xz
tar -xf pktgen-dpdk-pktgen-3.1.2.tar.gz
rm dpdk-16.11.1.tar.xz
rm pktgen-dpdk-pktgen-3.1.2.tar.gz
mv dpdk-stable-16.11.1/ dpdk16_11
mv pktgen-dpdk-pktgen-3.1.2/ pktgen_312

### git clone http://dpdk.org/git/dpdk
### git clone http://dpdk.org/git/apps/pktgen-dpdk
export RTE_SDK=$(pwd)/dpdk16_11
export PKTGEN=$(pwd)/pktgen_312
export RTE_TARGET=x86_64-native-linuxapp-gcc
cd $RTE_SDK
make install T=x86_64-native-linuxapp-gcc
cd $PKTGEN
make
modprobe uio
insmod $RTE_SDK/x86_64-native-linuxapp-gcc/kmod/igb_uio.ko
ifdown ens4
iface=`python3 $RTE_SDK/tools/dpdk-devbind.py -s | awk '/ens4/ {print $1}'`
python3 $RTE_SDK/tools/dpdk-devbind.py -b igb_uio $iface
#./app/app/x86_64-native-linuxapp-gcc/pktgen -c 0x3ff -n 2 --proc-type auto --socket-mem 4096 -- -T -P -m "[2-5:6-9].0"

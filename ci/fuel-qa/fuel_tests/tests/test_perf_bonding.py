import pytest
import os

from fuelweb_test import settings
from fuelweb_test.helpers.shaker import ShakerEngine
from fuelweb_test.settings import NEUTRON_SEGMENT
from fuelweb_test.settings import iface_alias
from fuelweb_test import logger
from copy import deepcopy

from fuelweb_test.testrail.performance_testrail_report import ShakerTestResultReporter


class TestPerfBonding(object):

    BOND_CONFIG = [
        {
            'mode': '802.3ad',
            'name': 'bond0',
            'slaves': [
                {'name': iface_alias('eth2')},
                {'name': iface_alias('eth3')}
            ],
            'type': 'bond',
            'assigned_networks': [],
            'bond_properties': {'lacp_rate': 'slow', 'type__': 'linux', 'mode': '802.3ad', 'xmit_hash_policy': 'layer3+4'},
            'interface_properties': {'dpdk': {'available': True, 'enabled': False}, 'disable_offloading': True, 'mtu': None},
            'offloading_modes': [{'state': True, 'name': 'l2-fwd-offload', 'sub': []}, {'state': True, 'name': 'rx-all', 'sub': []}, {'state': True, 'name': 'tx-nocache-copy', 'sub': []}, {'state': True, 'name': 'rx-vlan-filter', 'sub': []}, {'state': True, 'name': 'receive-hashing', 'sub': []}, {'state': True, 'name': 'ntuple-filters', 'sub': []}, {'state': True, 'name': 'tx-vlan-offload', 'sub': []}, {'state': True, 'name': 'rx-vlan-offload', 'sub': []}, {'state': True, 'name': 'large-receive-offload', 'sub': []}, {'state': True, 'name': 'generic-receive-offload', 'sub': []}, {'state': True, 'name': 'generic-segmentation-offload', 'sub': []}, {'state': True, 'name': 'tcp-segmentation-offload', 'sub': [{'state': True, 'name': 'tx-tcp6-segmentation', 'sub': []}, {'state': True, 'name': 'tx-tcp-segmentation', 'sub': []}]}, {'state': True, 'name': 'scatter-gather', 'sub': [{'state': True, 'name': 'tx-scatter-gather', 'sub': []}]}, {'state': True, 'name': 'tx-checksumming', 'sub': [{'state': True, 'name': 'tx-checksum-sctp', 'sub': []}, {'state': True, 'name': 'tx-checksum-ipv6', 'sub': []}, {'state': True, 'name': 'tx-checksum-ipv4', 'sub': []}]}, {'state': True, 'name': 'rx-checksumming', 'sub': []}]
        }
    ]

    INTERFACES = {
        'eno1': ['public', 'fuelweb_admin'],
        'bond0': ['storage', 'management', 'private']
    }

    def deploy_env(self, segmentation, dvr, l3ha, offloading):
        assert segmentation == "vlan" or segmentation == "tun"
        if dvr:
            assert not l3ha
        if l3ha:
            assert not dvr

        bond_config = deepcopy(TestPerfBonding.BOND_CONFIG)
        for mode in bond_config[0]["offloading_modes"]:
            mode["state"] = offloading

        # l2pop must be enabled in case of vxlan (tun) segmentation type
        l2pop = self.manager.env_config['network'].get('neutron-l2-pop', False)
        if segmentation == "tun":
            l2pop = True

        cluster_settings = {
            "sahara": self.manager.env_settings['components'].get('sahara', False),
            "ceilometer": self.manager.env_settings['components'].get('ceilometer', False),
            "ironic": self.manager.env_settings['components'].get('ironic', False),
            "user": self.manager.env_config.get("user", "admin"),
            "password": self.manager.env_config.get("password", "admin"),
            "tenant": self.manager.env_config.get("tenant", "admin"),
            "volumes_lvm": self.manager.env_settings['storages'].get("volume-lvm", False),
            "volumes_ceph": self.manager.env_settings['storages'].get("volume-ceph", False),
            "images_ceph": self.manager.env_settings['storages'].get("image-ceph", False),
            "ephemeral_ceph": self.manager.env_settings['storages'].get("ephemeral-ceph", False),
            "objects_ceph": self.manager.env_settings['storages'].get("rados-ceph", False),
            "osd_pool_size": str(self.manager.env_settings['storages'].get("replica-ceph", 2)),
            "net_provider": self.manager.env_config['network'].get('provider', 'neutron'),
            "net_segment_type": segmentation,
            "assign_to_all_nodes": self.manager.env_config['network'].get('pubip-to-all', False),
            "neutron_l3_ha": l3ha,
            "neutron_dvr": dvr,
            "neutron_l2_pop": l2pop
        }

        os.system("bash /home/mos-jenkins/workspace/env_17_run_shaker/revert_to_empty_state.sh")


        cluster_name = self.manager.env_config['name']
        snapshot_name = "ready_cluster_{}".format(cluster_name)

        nof_slaves = int(self.manager.full_config['template']['slaves'])
        assert self.manager.get_ready_slaves(nof_slaves)

        cluster_id = self.manager.fuel_web.create_cluster(
            name=self.manager.env_config['name'],
            mode=settings.DEPLOYMENT_MODE,
            release_name=self.manager.env_config['release'],
            settings=cluster_settings)

        self.assigned_slaves = set()
        self.manager._context._storage['cluster_id'] = cluster_id
        logger.info("Add nodes to env {}".format(cluster_id))
        names = "slave-{:02}"
        num = iter(xrange(1, nof_slaves + 1))
        nodes = {}
        for new in self.manager.env_config['nodes']:
            for _ in xrange(new['count']):
                name = names.format(next(num))
                while name in self.assigned_slaves:
                    name = names.format(next(num))

                self.assigned_slaves.add(name)
                nodes[name] = new['roles']
                logger.info("Set roles {} to node {}".format(new['roles'], name))

        self.manager.fuel_web.update_nodes(cluster_id, nodes)

        nailgun_nodes = self.manager.fuel_web.client.list_cluster_nodes(cluster_id)
        for node in nailgun_nodes:
            self.manager.fuel_web.update_node_networks(
                node['id'], interfaces_dict=deepcopy(TestPerfBonding.INTERFACES),
                raw_data=bond_config
            )
        self.manager.fuel_web.deploy_cluster_wait(cluster_id)
        self.manager.env.make_snapshot(snapshot_name, is_make=True)
        self.manager.env.resume_environment()

    @pytest.mark.scale_run_shaker
    def test_shaker(self):
        """ Deploys env several times with different configurations and runs shaker

        Scenario:
            1. Deploy env with parameters: segmentation=tun, dvr=on, l3ha=off, offloading=off
            2. Run shaker instance to instance
            3. Deploy env with parameters: segmentation=vlan, dvr=on, l3ha=off, offloading=off
            4. Run shaker instance to instance
            5. Deploy env with parameters: segmentation=tun, dvr=on, l3ha=off, offloading=on
            6. Run shaker instance to instance
            7. Deploy env with parameters: segmentation=vlan, dvr=on, l3ha=off, offloading=on
            8. Run shaker instance to instance
            9. Deploy env with parameters: segmentation=tun, dvr=off, l3ha=on, offloading=on
            10. Run shaker instance to instance
            11. Run shaker node to node
            12. Deploy env with parameters: segmentation=vlan, dvr=off, l3ha=on, offloading=on
            13. Run shaker instance to instance
            14. Run shaker node to node
            15. Send report
        """

        # KEY = (segmentation vlan/tun, dvr on/off, l3ha on/off, tcp offloading on/off, target nodes/instances)
        # def deploy_env(self, segmentation, dvr, l3ha, offloading)

        test_results = {}
        path_to_run_shaker_instances = os.environ.get('PATH_TO_RUN_SHAKER_BETWEEN_INSTANCES', 'faulty_path')
        path_to_run_shaker_nodes = os.environ.get('PATH_TO_RUN_SHAKER_BETWEEN_NODES', 'faulty_path')

        self.deploy_env("tun", True, False, False)

        admin_remote = self.manager.env.d_env.get_admin_remote()
        engine = ShakerEngine(admin_remote, path_to_run_shaker_instances, path_to_run_shaker_nodes)
        data = engine.start_shaker_test()
        test_results[("tun", True, False, False, "instances")] = data

        self.deploy_env("vlan", True, False, False)

        admin_remote = self.manager.env.d_env.get_admin_remote()
        engine = ShakerEngine(admin_remote, path_to_run_shaker_instances, path_to_run_shaker_nodes)
        data = engine.start_shaker_test()
        test_results[("vlan", True, False, False, "instances")] = data

        self.deploy_env("tun", True, False, True)

        admin_remote = self.manager.env.d_env.get_admin_remote()
        engine = ShakerEngine(admin_remote, path_to_run_shaker_instances, path_to_run_shaker_nodes)
        data = engine.start_shaker_test()
        test_results[("tun", True, False, True, "instances")] = data

        self.deploy_env("vlan", True, False, True)

        admin_remote = self.manager.env.d_env.get_admin_remote()
        engine = ShakerEngine(admin_remote, path_to_run_shaker_instances, path_to_run_shaker_nodes)
        data = engine.start_shaker_test()
        test_results[("vlan", True, False, True, "instances")] = data

        self.deploy_env("tun", False, True, True)

        admin_remote = self.manager.env.d_env.get_admin_remote()
        engine = ShakerEngine(admin_remote, path_to_run_shaker_instances, path_to_run_shaker_nodes)
        data = engine.start_shaker_test()
        test_results[("tun", False, True, True, "instances")] = data

        admin_remote = self.manager.env.d_env.get_admin_remote()
        engine = ShakerEngine(admin_remote, path_to_run_shaker_instances, path_to_run_shaker_nodes)
        data = engine.start_shaker_test(between_nodes=True)
        test_results[("tun", False, True, True, "nodes")] = data

        self.deploy_env("vlan", False, True, True)

        admin_remote = self.manager.env.d_env.get_admin_remote()
        engine = ShakerEngine(admin_remote, path_to_run_shaker_instances, path_to_run_shaker_nodes)
        data = engine.start_shaker_test()
        test_results[("vlan", False, True, True, "instances")] = data

        admin_remote = self.manager.env.d_env.get_admin_remote()
        engine = ShakerEngine(admin_remote, path_to_run_shaker_instances, path_to_run_shaker_nodes)
        data = engine.start_shaker_test(between_nodes=True)
        test_results[("vlan", False, True, True, "nodes")] = data

        reporter = ShakerTestResultReporter(test_results)
        reporter.send_report()

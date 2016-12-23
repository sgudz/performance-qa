#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import pytest
import re
import os
import os.path
import json

from fuelweb_test import logger
from fuelweb_test import settings
from fuelweb_test.helpers import checkers
from fuelweb_test.helpers import os_actions
from fuelweb_test.helpers import common
from fuelweb_test.helpers.ssh_manager import SSHManager
from fuelweb_test.helpers.rally import RallyBenchmarkTest
from fuelweb_test.helpers.rally import RallyTask 

# pylint: disable=no-member
ssh_manager = SSHManager()

@pytest.fixture
def set_test_description(request):
   name =  request._pyfuncitem._genid
   pattern = "Execute Rally scenario {}"
   request.function.__func__.__doc__ = pattern.format(name)

@pytest.fixture(scope='function', autouse=False)
def prepare(request):
    " Redefining fixture in order to have cluster deployment check only once"
    pass

@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    print items

@pytest.fixture(scope='class')
def rally_setup(request):
        values = {
            'concurrency': 5,
            'gre_enabled': False,
            'floating_net': 'admin_floating_net'
        }
        rally_scenarios  = os.environ.get("RALLY_SCENARIOS_PATH")
        rally_scenarios = os.path.normpath(rally_scenarios)


        fuel_web = request.cls.manager.fuel_web
        cluster_id = fuel_web.get_last_created_cluster()
        computes = fuel_web.get_nailgun_cluster_nodes_by_roles(cluster_id=cluster_id, roles=["compute"])
        values['compute'] = len(computes)

        cluster_vip = fuel_web.get_public_vip(cluster_id)
        os_conn = os_actions.OpenStackActions(cluster_vip, 'admin', 'admin', 'admin')
        if not os_conn.get_flavor_by_name('m1.nano'):
            os_conn.create_flavor('m1.nano', 64, 1, 0, flavorid='41')

        floating_list = fuel_web.get_cluster_floating_list(os_conn, cluster_id)

        vlans = fuel_web.client.get_cluster_vlans(cluster_id)
        vlan_amount = vlans[1] - vlans[0]
        floating_ip_amount = len(floating_list)

        values['vlan_amount'] = vlan_amount
        values['floating_ip_amount'] = floating_ip_amount
        values['horizon_base_url'] = "http://{}/horizon/".format(cluster_vip)
        rel_path = os.path.dirname(rally_scenarios)
        values['current_path'] = os.path.relpath(os.path.join(rally_scenarios, 'heat/'), rel_path)

        with open('rally_args.json', 'w') as args_file:
              json.dump(values, args_file)

        benchmark = RallyBenchmarkTest(
                container_repo=settings.RALLY_DOCKER_REPO,
                environment=request.cls.manager.env,
                cluster_id=cluster_id,
                test_type="empty",
                rally_args=values
        )
        benchmark.engine.admin_remote.upload('rally_args.json', benchmark.engine.dir_for_home)
        benchmark.engine.admin_remote.upload(rally_scenarios, benchmark.engine.dir_for_home)
        request.cls.benchmark = benchmark

@pytest.mark.need_ready_cluster
@pytest.mark.usefixtures("rally_setup")
@pytest.mark.usefixtures("set_test_description")
class TestPerfSmoke(object):
    """Test class for the test group devoted to the load tests.

    Contains test case with cluster in HA mode with ceph,
    launching Rally and cold restart of all nodes.

    """
    cluster_config = {}

    @pytest.mark.scale_ci
    def test_perf_ci(self):
        "Deploy cluster and run OSTF"

        #request.cls.manager.get_ready_cluster()
        cluster_id = self._storage['cluster_id']
        fuel_web = self.manager.fuel_web

        cluster = fuel_web.client.get_cluster(cluster_id)
        assert str(cluster['net_provider']) == settings.NEUTRON

        fuel_web.verify_network(cluster_id)
        fuel_web.run_ostf(cluster_id=cluster_id)

       
    #@pytest.mark.skip_preparation
    @pytest.mark.scale_ci2
    def test_run_rally_light(self, rally_scenario):
        "Run Rally Scenario"
        bench = self.benchmark
        bench.current_task = RallyTask(bench.deployment, rally_scenario, bench.rally_args)
        logger.info('Starting Rally benchmark test {}'.format(rally_scenario))
        logfile = bench.current_task.start()
        results = bench.current_task.get_results()
        bench.engine.admin_remote.download(os.path.join(bench.engine.dir_for_home, logfile), './rally_logs/')

        assert results, "Test {} returned no results! See log for details".format(rally_scenario)
        results = json.loads(results)
        fails = []
        for test in results:
            fails.extend(sla for sla in test["sla"] if not sla['success'])
        assert len(fails) == 0, "SLA failed: {}".format(";".join(sla['detail'] for sla in fails))


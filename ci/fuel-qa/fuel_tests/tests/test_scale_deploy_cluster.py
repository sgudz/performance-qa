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

import os
import pytest

from fuelweb_test import logger
from fuelweb_test import settings
from fuelweb_test.helpers.ssh_manager import SSHManager

@pytest.mark.need_ready_cluster
class TestScaleDeployCluster(object):
    "Test class for the test group devoted to the load tests."

    cluster_config = {}
   
    @pytest.mark.scale_deploy_cluster
    def test_scale_deploy_cluster(self):
        "Deploy cluster and run OSTF"
        
        cluster_id = self._storage['cluster_id']
        fuel_web = self.manager.fuel_web

        cluster = fuel_web.client.get_cluster(cluster_id)
        assert str(cluster['net_provider']) == settings.NEUTRON


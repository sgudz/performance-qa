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

# pylint: disable=no-member
ssh_manager = SSHManager()

@pytest.mark.need_ready_master
class TestPrepareFuelMaster(object):
    "Make necessary changes to Fuel Master before creating cluster"

    @pytest.mark.scale_deploy_master
    def test_prepare_fuel_master(self):
        """Configure external IP address and routing"""

        ssh = self.manager.env.ssh_manager
        admin_ip = os.environ.get('FUEL_IP', 'faulty_ip')
        admin_if = 'enp0s4'
        admin_netmask='255.255.252.0'
        add_admin_ip = ('DEVICE="{0}"\\n'
                        'ONBOOT="yes"\\n'
                        'NM_CONTROLLED="no"\\n'
                        'GATEWAY="172.16.44.1"\\n'
                        'DEFROUTE=yes\\n'
                        'BOOTPROTO=static\\n'
                        'IPADDR={1}\\n'
                        'NETMASK={2}\\n').format(admin_if,
                                                 admin_ip,
                                                 admin_netmask)
        cmd = ('echo -e "{0}" > /etc/sysconfig/network-scripts/ifcfg-{1};'
               'ifup {1}; ip -o -4 a s {1} | grep -w {2}').format(
            add_admin_ip, admin_if, admin_ip)
        logger.info('Trying to assign {0} IP to the {1} on master node...'.
                     format(admin_ip, admin_if))

        result = ssh.execute_on_remote(ip=ssh.admin_ip, cmd=cmd)
        assert result['exit_code'] ==  0, ('Failed to assign external '
                     'IP address on master node: {0}').format(result)
        logger.debug('Done: {0}'.format(result['stdout']))

        self.env.make_snapshot("empty", is_make=True)

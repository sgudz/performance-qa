import json

from fuelweb_test import logger
from devops.helpers.helpers import wait

class ShakerEngine(object):

    REMOTE_PATH_TO_RUN_SHAKER_BETWEEN_INSTANCES = "/root/run_shaker_instances.sh"
    REMOTE_PATH_TO_RUN_SHAKER_BETWEEN_NODES = "/root/run_shaker_nodes.sh"
    REMOTE_PATH_TO_TEST_STATUS = "/root/shaker_test_status.txt"
    REMOTE_PATH_TO_TEST_RESULT = "/root/results.json"
    FILES_TO_CLEANUP = [
        "/root/nodes*",
        REMOTE_PATH_TO_TEST_RESULT,
        REMOTE_PATH_TO_RUN_SHAKER_BETWEEN_INSTANCES,
        REMOTE_PATH_TO_RUN_SHAKER_BETWEEN_NODES,
        REMOTE_PATH_TO_TEST_STATUS,
        "/root/traffic.py",
        "/root/VMs.yaml"
    ]

    def __init__(self,
                 admin_remote,
                 path_to_run_shaker_instances,
                 path_to_run_shaker_nodes):
        self.admin_remote = admin_remote

        self.admin_remote.upload(path_to_run_shaker_instances, ShakerEngine.REMOTE_PATH_TO_RUN_SHAKER_BETWEEN_INSTANCES)
        self.admin_remote.upload(path_to_run_shaker_nodes, ShakerEngine.REMOTE_PATH_TO_RUN_SHAKER_BETWEEN_NODES)

    @property
    def current_test_status(self):
        cmd = "cat {}".format(ShakerEngine.REMOTE_PATH_TO_TEST_STATUS)
        result = self.admin_remote.execute(cmd)
        assert result["exit_code"] == 0
        logger.info(result["stdout"][0].strip('\n'))
        return result["stdout"][0].strip('\n')

    def start_shaker_test(self, between_nodes = False):
        cmd = "screen -dm bash {}".format(ShakerEngine.REMOTE_PATH_TO_RUN_SHAKER_BETWEEN_INSTANCES)
        if between_nodes:
            cmd = "screen -dm bash {}".format(ShakerEngine.REMOTE_PATH_TO_RUN_SHAKER_BETWEEN_NODES)

        result = self.admin_remote.execute(cmd)
        assert result["exit_code"] == 0
        wait(lambda: self.current_test_status == 'running', timeout=10, timeout_msg='Shaker test timeout')
        logger.info("Shaker test is running")

        wait(lambda: self.current_test_status == 'finished', timeout=900, timeout_msg='Shaker test timeout')
        logger.info("Shaker test is finished")

        cmd = "cat {}".format(ShakerEngine.REMOTE_PATH_TO_TEST_RESULT)
        result = self.admin_remote.execute(cmd)
        assert result["exit_code"] == 0
        logger.info(result["stdout"])
        data = json.loads(result["stdout"][0])
        logger.info(data)

        for file in ShakerEngine.FILES_TO_CLEANUP:
            cmd = "/bin/rm -f {}".format(file)
            result = self.admin_remote.execute(cmd)
            assert result["exit_code"] == 0

        return data

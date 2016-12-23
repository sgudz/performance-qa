import json

from fuelweb_test import logger
from devops.helpers.helpers import wait

class WallyEngine(object):

    REMOTE_PATH_TO_RUN_WALLY = "/root/run_wally.sh"
    REMOTE_PATH_TO_TEST_STATUS = "/root/wally_test_status.txt"
    REMOTE_PATH_TO_TEST_RESULT = "/root/results.json"
    FILES_TO_CLEANUP = [
        "/root/test1.yaml"
    ]

    def __init__(self,
                 admin_remote,
                 path_to_run_wally):
        self.admin_remote = admin_remote

        self.admin_remote.upload(path_to_run_wally, WallyEngine.REMOTE_PATH_TO_RUN_WALLY)

#    @property
#    def current_test_status(self):
#        cmd = "cat {}".format(WallyEngine.REMOTE_PATH_TO_TEST_STATUS)
#        result = self.admin_remote.execute(cmd)
#        assert result["exit_code"] == 0
#        logger.info(result["stdout"][0].strip('\n'))
#        return result["stdout"][0].strip('\n')

    def start_wally_test(self):
        cmd = "screen -dm bash {}".format(WallyEngine.REMOTE_PATH_TO_RUN_WALLY)

        result = self.admin_remote.execute(cmd)
#        assert result["exit_code"] == 0
#        wait(lambda: self.current_test_status == 'running', timeout=10, timeout_msg='Wally test timeout')
#        logger.info("Wally test is running")
#
#        wait(lambda: self.current_test_status == 'finished', timeout=900, timeout_msg='Wally test timeout')
#        logger.info("Wally test is finished")

#        cmd = "cat {}".format(WallyEngine.REMOTE_PATH_TO_TEST_RESULT)
#        result = self.admin_remote.execute(cmd)
#        assert result["exit_code"] == 0
#        logger.info(result["stdout"])
        data = json.loads(result["stdout"][0])
        logger.info(data)

        for file in WallyEngine.FILES_TO_CLEANUP:
            cmd = "/bin/rm -f {}".format(file)
            result = self.admin_remote.execute(cmd)
#            assert result["exit_code"] == 0

        return data

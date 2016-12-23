import os
import pytest
from fuelweb_test.helpers.shaker import ShakerEngine

@pytest.mark.scale_shaker
class TestScaleShaker(object):

    def test_run_shaker(self):
        """OLOLO!

        Scenario:
            1. Ololo

        Duration ololoshechka
        Snapshot mr. ololoshka
        """

        path_to_run_shaker = os.environ.get('PATH_TO_RUN_SHAKER', 'faulty_ip')
        admin_remote = self.env.d_env.get_admin_remote()

        engine = ShakerEngine(admin_remote, path_to_run_shaker)
        engine.start_shaker_test()
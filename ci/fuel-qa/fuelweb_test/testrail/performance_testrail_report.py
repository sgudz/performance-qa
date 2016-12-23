import os
import numpy

from fuelweb_test import logger
from fuelweb_test.testrail.testrail_client import TestRailProject


class TestResult(object):
    def __init__(self, test_status_to_id):
        self.test_status_to_id = test_status_to_id

        self.status = None
        self.duration = None
        self.version = None
        self.description = None
        self.url = None
        self.comments = None
        self.steps = None


class ShakerTestResult(TestResult):
    def __init__(self, conf, json_data, test_status_to_id):
        super(ShakerTestResult, self).__init__(test_status_to_id)

        self.conf = conf
        self.json_data = json_data

        self.status = "passed"

        # hardcoded
        self.duration = "300s"

        # hardcoded
        self.version = "1"

        self.description = self.get_description()

        # hardcoded
        self.url = None

        # hardcoded
        self.comments = None

        self.steps = self.get_steps()

    def get_description(self):
        return "dumb description"

    def get_steps(self):
        median = -1
        stdev = -1

        items = [each for each in self.json_data['records']]
        for i in range(len(items)):
            try:
                median = int(round(self.json_data['records'][items[i]]['stats']['bandwidth']['median'], 0))
                stdev = int(round(self.json_data['records'][items[i]]['stats']['bandwidth']['stdev'], 0))
            except KeyError:
                continue

        if median == -1 or stdev == -1:
            logger.error("Failed shaker scenario! There are no steps to send to testrail.")
            self.status = "failed"
            return None

        median_status_id = self.test_status_to_id["passed"]
        median_expected = float(ShakerTestResultReporter.expected_values[self.conf][0])
        if median < float(median_expected) * 0.9:
            median_status_id = self.test_status_to_id["failed"]
            self.status = "failed"

        stdev_status_id = self.test_status_to_id["passed"]
        stdev_expected = float(ShakerTestResultReporter.expected_values[self.conf][1])
        if stdev > float(stdev_expected) * 0.5:
            stdev_status_id = self.test_status_to_id["failed"]

        return [{"content": "Check [network bandwidth, Median; Mbps]",
                 "status_id": str(median_status_id),
                 "expected": str(median_expected),
                 "actual": str(median)},
                {"content": "Check [deviation; pcs]",
                 "status_id": str(stdev_status_id),
                 "expected": str(stdev_expected),
                 "actual": str(stdev)}]


class RallyTestResult(TestResult):
    def __init__(self, json_data, test_status_to_id):
        super(RallyTestResult, self).__init__(test_status_to_id)

        self.json_data = json_data

        self.success = True
        for sla in json_data["sla"]:
            self.success &= sla["success"]

        self.duration = "%.0fs" % json_data["full_duration"]

        # hardcoded
        self.version = "1"

        self.description = self.get_description()

        # hardcoded
        self.url = None

        # hardcoded
        self.comments = None

        self.steps = self.get_steps()

    def get_description(self):
        return "ololo"

    def get_steps(self):
        return None


class HorizonTestResult(RallyTestResult):
    def __init__(self, json_data, test_status_to_id):
        super(HorizonTestResult, self).__init__(json_data, test_status_to_id)

    @property
    def page(self):
        return self.json_data["key"]["kw"]["args"]["page"]

    @property
    def number_of_objects(self):
        return self.json_data["key"]["kw"]["context"]["selenium"]["items_per_page"]

    def get_description(self):
        return "%s - %s - %s" % (self.json_data["key"]["name"], self.page, self.number_of_objects)

    def get_steps(self):
        if len(self.json_data["result"]) == 0:
            return None

        expected = float(HorizonTestResultReporter.expected_values[self.page][self.number_of_objects])

        times = []
        for result in self.json_data["result"]:
            times.append(result["atomic_actions"]["horizon_performance.open_page"])
        actual = numpy.percentile(times, 90)

        status_id = self.test_status_to_id["passed"]
        if actual > expected:
            status_id = self.test_status_to_id["failed"]

        return [{
            "content": "Check [response_time; 90_percentile_s]",
            "status_id": str(status_id),
            "expected": str(expected),
            "actual": str(actual)
        }]


class TestResultReporter(object):
    project = TestRailProject("https://mirantis.testrail.com", "pshvetsov@mirantis.com", "UFSvw69f",
                              "Mirantis OpenStack")

    def __init__(self):
        self.test_results = []
        self.test_status_to_id = self.get_status_mapping()

    def get_status_mapping(self):
        mapping = {}
        mapping["passed"] = TestResultReporter.project.get_status("passed")["id"]
        mapping["failed"] = TestResultReporter.project.get_status("failed")["id"]
        return mapping


class ShakerTestResultReporter(TestResultReporter):
    cases = TestResultReporter.project.get_cases(4259)

    # KEY = (segmentation vlan/tun, dvr on/off, l3ha on/off, tcp offloading on/off, target nodes/instances)
    expected_values = {}

    # GROUP: TCP offloading: OFF; DVR:ON
    steps = [item for item in cases if item["title"] == "Neutron VxLAN Instance-to-Instance; bonding: on; Ubuntu"][0][
        "custom_test_case_steps"]
    band = [item for item in steps if "bandwidth" in item["content"]][0]["expected"]
    dev = [item for item in steps if "deviation" in item["content"]][0]["expected"]
    expected_values[("tun", True, False, False, "instances")] = [band, dev]

    steps = [item for item in cases if item["title"] == "Neutron VLAN Instance-to-Instance; bonding: on; Ubuntu"][0][
        "custom_test_case_steps"]
    band = [item for item in steps if "bandwidth" in item["content"]][0]["expected"]
    dev = [item for item in steps if "deviation" in item["content"]][0]["expected"]
    expected_values[("vlan", True, False, False, "instances")] = [band, dev]

    # GROUP: TCP offloading: ON; DVR:ON
    steps = \
    [item for item in cases if item["title"] == "Neutron VxLAN Instance-to-Instance; DVR on, bonding: on; Ubuntu"][0][
        "custom_test_case_steps"]
    band = [item for item in steps if "bandwidth" in item["content"]][0]["expected"]
    dev = [item for item in steps if "deviation" in item["content"]][0]["expected"]
    expected_values[("tun", True, False, True, "instances")] = [band, dev]

    steps = \
    [item for item in cases if item["title"] == "Neutron VLAN Instance-to-Instance; DVR on, bonding: on; Ubuntu"][0][
        "custom_test_case_steps"]
    band = [item for item in steps if "bandwidth" in item["content"]][0]["expected"]
    dev = [item for item in steps if "deviation" in item["content"]][0]["expected"]
    expected_values[("vlan", True, False, True, "instances")] = [band, dev]

    # GROUP: TCP offloading: ON: Neutron L3 HA: ON
    steps = [item for item in cases if item["title"] == "Neutron VxLAN Node-to-Node; L3 HA on, bonding: on; Ubuntu"][0][
        "custom_test_case_steps"]
    band = [item for item in steps if "bandwidth" in item["content"]][0]["expected"]
    dev = [item for item in steps if "deviation" in item["content"]][0]["expected"]
    expected_values[("tun", False, True, True, "nodes")] = [band, dev]

    steps = \
    [item for item in cases if item["title"] == "Neutron VxLAN Instance-to-Instance; L3 HA on, bonding: on; Ubuntu"][0][
        "custom_test_case_steps"]
    band = [item for item in steps if "bandwidth" in item["content"]][0]["expected"]
    dev = [item for item in steps if "deviation" in item["content"]][0]["expected"]
    expected_values[("tun", False, True, True, "instances")] = [band, dev]

    steps = [item for item in cases if item["title"] == "Neutron VLAN Node-to-Node; L3 HA on, bonding: on; Ubuntu"][0][
        "custom_test_case_steps"]
    band = [item for item in steps if "bandwidth" in item["content"]][0]["expected"]
    dev = [item for item in steps if "deviation" in item["content"]][0]["expected"]
    expected_values[("vlan", False, True, True, "nodes")] = [band, dev]

    steps = \
    [item for item in cases if item["title"] == "Neutron VLAN Instance-to-Instance; L3 HA on, bonding: on; Ubuntu"][0][
        "custom_test_case_steps"]
    band = [item for item in steps if "bandwidth" in item["content"]][0]["expected"]
    dev = [item for item in steps if "deviation" in item["content"]][0]["expected"]
    expected_values[("vlan", False, True, True, "instances")] = [band, dev]

    def __init__(self, data):
        super(ShakerTestResultReporter, self).__init__()
        for conf, json_data in data.items():
            self.test_results.append(ShakerTestResult(conf, json_data, self.test_status_to_id))

    def test_to_conf(self, test):
        if test["title"] == "Neutron VxLAN Instance-to-Instance; bonding: on; Ubuntu":
            return ("tun", True, False, False, "instances")
        if test["title"] == "Neutron VLAN Instance-to-Instance; bonding: on; Ubuntu":
            return ("vlan", True, False, False, "instances")
        if test["title"] == "Neutron VxLAN Instance-to-Instance; DVR on, bonding: on; Ubuntu":
            return ("tun", True, False, True, "instances")
        if test["title"] == "Neutron VLAN Instance-to-Instance; DVR on, bonding: on; Ubuntu":
            return ("vlan", True, False, True, "instances")
        if test["title"] == "Neutron VxLAN Node-to-Node; L3 HA on, bonding: on; Ubuntu":
            return ("tun", False, True, True, "nodes")
        if test["title"] == "Neutron VLAN Node-to-Node; L3 HA on, bonding: on; Ubuntu":
            return ("tun", False, True, True, "instances")
        if test["title"] == "Neutron VxLAN Instance-to-Instance; L3 HA on, bonding: on; Ubuntu":
            return ("vlan", False, True, True, "nodes")
        if test["title"] == "Neutron VLAN Instance-to-Instance; L3 HA on, bonding: on; Ubuntu":
            return ("vlan", False, True, True, "instances")
        return None

    def send_report(self):
        milestone = os.environ.get("MILESTONE", "9.1")
        suite_id = os.environ.get("SUITE_ID", "4259")
        snapshot = os.environ.get("SNAPSHOT", "000")

        milestones = TestResultReporter.project.get_milestones()
        milestone_id = [m for m in milestones if m["name"] == milestone][0]["id"]
        run = TestResultReporter.project.test_run_struct(name="{} snapshot #{}".format(milestone, snapshot),
                                                         suite_id=suite_id,
                                                         description="to delete",
                                                         milestone_id=milestone_id,
                                                         config_ids=None)
        run = TestResultReporter.project.add_run(run)

        tests = TestResultReporter.project.get_tests(run["id"])

        for test_result in self.test_results:
            for test in tests:
                if self.test_to_conf(test) == test_result.conf:
                    test_id = test["id"]
            TestResultReporter.project.add_results_for_test(test_id, test_result)

class RallyResultReporter(TestResultReporter):
    def __init__(self):
        super(RallyResultReporter, self).__init__()


class HorizonTestResultReporter(RallyResultReporter):
    cases = TestResultReporter.project.get_cases(4308)
    expected_values = {
        "project/images": {
            100: (item for item in cases if item["id"] == 1673818).next()["custom_test_case_steps"][0]["expected"],
            500: (item for item in cases if item["id"] == 1673819).next()["custom_test_case_steps"][0]["expected"]
        },
        "admin/volumes": {
            100: (item for item in cases if item["id"] == 1673820).next()["custom_test_case_steps"][0]["expected"],
            500: (item for item in cases if item["id"] == 1673821).next()["custom_test_case_steps"][0]["expected"]
        },
        "identity/users": {
            100: (item for item in cases if item["id"] == 1673824).next()["custom_test_case_steps"][0]["expected"],
            500: (item for item in cases if item["id"] == 1673825).next()["custom_test_case_steps"][0]["expected"]
        },
        "identity": {
            100: (item for item in cases if item["id"] == 1673826).next()["custom_test_case_steps"][0]["expected"],
            500: (item for item in cases if item["id"] == 1673827).next()["custom_test_case_steps"][0]["expected"]
        },
        "admin/instances": {
            100: (item for item in cases if item["id"] == 1673828).next()["custom_test_case_steps"][0]["expected"],
            500: (item for item in cases if item["id"] == 1673829).next()["custom_test_case_steps"][0]["expected"]
        },
        "admin/networks": {
            100: (item for item in cases if item["id"] == 1673830).next()["custom_test_case_steps"][0]["expected"],
            500: (item for item in cases if item["id"] == 1673831).next()["custom_test_case_steps"][0]["expected"]
        },
        "admin/images": {
            100: None,
            500: None
        },
        "project/instances": {
            100: (item for item in cases if item["id"] == 1681254).next()["custom_test_case_steps"][0]["expected"],
            500: (item for item in cases if item["id"] == 1681255).next()["custom_test_case_steps"][0]["expected"]
        },
        "project/flavors": {
            100: None,
            500: None
        },
        "admin/volume_snapshots": {
            100: None,
            500: None
        },
        "admin/routers": {
            100: None,
            500: None
        },
        "project/volumes": {
            100: None,
            500: None
        }
    }

    def __init__(self, data):
        super(HorizonTestResultReporter, self).__init__()
        for json_result in data:
            self.test_results.append(HorizonTestResult(json_result, self.test_status_to_id))


# data = None
# with open("/home/ilozgach/sys_test.log") as f:
#     data = f.read()
#
# reporter = HorizonTestResultReporter(json.loads(data))

# data = {
#     ("tun", True, False, False, "instances"): {u'scenarios': {u'OpenStack L2 Performance': {u'file_name': u'/usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml', u'deployment': {u'agents': [{u'ip': u'192.168.170.4', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, {u'ip': u'192.168.170.3', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}]}, u'execution': {u'tests': [{u'time': 30, u'threads': 22, u'class': u'iperf_graph', u'title': u'TCP_threads_22'}]}, u'description': u'This scenario tests network between different compute nodes.', u'title': u'OpenStack L2 Performance'}}, u'records': {u'354854cc-cd8a-41ca-a170-a44abcf1d07b': {u'stats': {u'bandwidth': {u'max': 12188.0, u'min': 11324.0, u'unit': u'Mbit/s', u'mean': 11890.51724137931}}, u'scenario': u'OpenStack L2 Performance', u'concurrency': 1, u'test': u'TCP_threads_22', u'x-chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 12089.0, 11937.0, 12115.0, 12023.0, 12072.0, 11977.0, 12155.0, 11904.0, 11890.0, 12057.0, 11520.0, 11889.0, 12133.0, 11550.0, 12098.0, 11324.0, 12188.0, 11919.0, 11915.0, 11847.0, 11782.0, 11674.0, 11665.0, 11683.0, 11686.0, 11901.0, 11907.0, 11824.0, 12101.0]], u'type': u'concurrency', u'id': u'354854cc-cd8a-41ca-a170-a44abcf1d07b', u'node_chart': [[u'x', None], [u'Mean bandwidth', 11890.51724137931], [u'Max bandwidth', 12188.0], [u'Min bandwidth', 11324.0]]}, u'4efcfcb1-edaf-4a0d-9820-c1e2fc8a8f44': {u'status': u'ok', u'node': None, u'finish': 1474043192.354641, u'stats': {u'bandwidth': {u'min': 11324.0, u'max': 12188.0, u'median': 11907.0, u'stdev': 209.019385341, u'unit': u'Mbit/s', u'mean': 11890.51724137931}}, u'concurrency': 1, u'scenario': u'OpenStack L2 Performance', u'schedule': 1474043162.294499, u'chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 12089.0, 11937.0, 12115.0, 12023.0, 12072.0, 11977.0, 12155.0, 11904.0, 11890.0, 12057.0, 11520.0, 11889.0, 12133.0, 11550.0, 12098.0, 11324.0, 12188.0, 11919.0, 11915.0, 11847.0, 11782.0, 11674.0, 11665.0, 11683.0, 11686.0, 11901.0, 11907.0, 11824.0, 12101.0]], u'agent': u'a-001', u'id': u'4efcfcb1-edaf-4a0d-9820-c1e2fc8a8f44', u'start': 1474043162.304561, u'meta': [[u'time', u's'], [u'bandwidth', u'Mbit/s']], u'command': {u'type': u'program', u'data': u'iperf --client 192.168.170.3 --format m --time 30 --parallel 22 --interval 1 --nodelay --reportstyle C'}, u'samples': [[1.0, 12089.0], [2.0, 11937.0], [3.0, 12115.0], [4.0, 12023.0], [5.0, 12072.0], [6.0, 11977.0], [7.0, 12155.0], [8.0, 11904.0], [9.0, 11890.0], [10.0, 12057.0], [11.0, 11520.0], [12.0, 11889.0], [13.0, 12133.0], [14.0, 11550.0], [15.0, 12098.0], [16.0, 11324.0], [17.0, 12188.0], [18.0, 11919.0], [19.0, 11915.0], [20.0, 11847.0], [21.0, 11782.0], [22.0, 11674.0], [23.0, 11665.0], [24.0, 11683.0], [25.0, 11686.0], [26.0, 11901.0], [27.0, 11907.0], [28.0, 11824.0], [29.0, 12101.0]], u'executor': u'iperf_graph', u'test': u'TCP_threads_22', u'type': u'agent', u'stderr': u''}, u'55b84287-7727-42ac-b410-993edd876191': {u'test': u'TCP_threads_22', u'type': u'test', u'chart': [[u'Mean bandwidth', 11890.51724137931], [u'x', 1]], u'scenario': u'OpenStack L2 Performance', u'id': u'55b84287-7727-42ac-b410-993edd876191'}}, u'tests': {u'TCP_threads_22': {u'title': u'TCP_threads_22', u'interval': 1, u'threads': 22, u'time': 30, u'csv': True, u'class': u'iperf_graph'}}, u'agents': {u'a-002': {u'ip': u'192.168.170.3', u'master_id': u'a-001', u'master': {u'ip': u'192.168.170.4', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, u'id': u'a-002', u'mode': u'slave'}, u'a-001': {u'ip': u'192.168.170.4', u'slave_id': u'a-002', u'slave': {u'ip': u'192.168.170.3', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}, u'id': u'a-001', u'mode': u'master'}}, u'sla': []},
#     ("vlan", True, False, False, "instances"): {u'scenarios': {u'OpenStack L2 Performance': {u'file_name': u'/usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml', u'deployment': {u'agents': [{u'ip': u'192.168.171.2', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, {u'ip': u'192.168.171.4', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}]}, u'execution': {u'tests': [{u'time': 30, u'threads': 22, u'class': u'iperf_graph', u'title': u'TCP_threads_22'}]}, u'description': u'This scenario tests network between different compute nodes.', u'title': u'OpenStack L2 Performance'}}, u'records': {u'5a4244ea-a511-4bcf-8a9b-9ad9ff4a1552': {u'status': u'ok', u'node': None, u'finish': 1474047433.58464, u'stats': {u'bandwidth': {u'min': 11940.0, u'max': 13422.0, u'median': 12797.0, u'stdev': 405.264196501, u'unit': u'Mbit/s', u'mean': 12718.551724137931}}, u'concurrency': 1, u'scenario': u'OpenStack L2 Performance', u'schedule': 1474047403.518734, u'chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 12797.0, 13422.0, 13119.0, 13237.0, 13052.0, 13044.0, 13016.0, 13148.0, 12938.0, 12982.0, 12777.0, 13021.0, 12772.0, 12937.0, 12787.0, 13039.0, 12843.0, 12951.0, 12270.0, 12746.0, 11940.0, 12143.0, 12047.0, 12239.0, 12197.0, 12561.0, 12237.0, 12240.0, 12336.0]], u'agent': u'a-001', u'id': u'5a4244ea-a511-4bcf-8a9b-9ad9ff4a1552', u'start': 1474047403.528843, u'meta': [[u'time', u's'], [u'bandwidth', u'Mbit/s']], u'command': {u'type': u'program', u'data': u'iperf --client 192.168.171.4 --format m --time 30 --parallel 22 --interval 1 --nodelay --reportstyle C'}, u'samples': [[1.0, 12797.0], [2.0, 13422.0], [3.0, 13119.0], [4.0, 13237.0], [5.0, 13052.0], [6.0, 13044.0], [7.0, 13016.0], [8.0, 13148.0], [9.0, 12938.0], [10.0, 12982.0], [11.0, 12777.0], [12.0, 13021.0], [13.0, 12772.0], [14.0, 12937.0], [15.0, 12787.0], [16.0, 13039.0], [17.0, 12843.0], [18.0, 12951.0], [19.0, 12270.0], [20.0, 12746.0], [21.0, 11940.0], [22.0, 12143.0], [23.0, 12047.0], [24.0, 12239.0], [25.0, 12197.0], [26.0, 12561.0], [27.0, 12237.0], [28.0, 12240.0], [29.0, 12336.0]], u'executor': u'iperf_graph', u'test': u'TCP_threads_22', u'type': u'agent', u'stderr': u''}, u'8d9efcaa-b8e2-4874-8236-5108c7b23085': {u'stats': {u'bandwidth': {u'max': 13422.0, u'min': 11940.0, u'unit': u'Mbit/s', u'mean': 12718.551724137931}}, u'scenario': u'OpenStack L2 Performance', u'concurrency': 1, u'test': u'TCP_threads_22', u'x-chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 12797.0, 13422.0, 13119.0, 13237.0, 13052.0, 13044.0, 13016.0, 13148.0, 12938.0, 12982.0, 12777.0, 13021.0, 12772.0, 12937.0, 12787.0, 13039.0, 12843.0, 12951.0, 12270.0, 12746.0, 11940.0, 12143.0, 12047.0, 12239.0, 12197.0, 12561.0, 12237.0, 12240.0, 12336.0]], u'type': u'concurrency', u'id': u'8d9efcaa-b8e2-4874-8236-5108c7b23085', u'node_chart': [[u'x', None], [u'Mean bandwidth', 12718.551724137931], [u'Max bandwidth', 13422.0], [u'Min bandwidth', 11940.0]]}, u'9be09037-62ff-45db-80b4-a7cc4a3e9d23': {u'test': u'TCP_threads_22', u'type': u'test', u'chart': [[u'Mean bandwidth', 12718.551724137931], [u'x', 1]], u'scenario': u'OpenStack L2 Performance', u'id': u'9be09037-62ff-45db-80b4-a7cc4a3e9d23'}}, u'tests': {u'TCP_threads_22': {u'title': u'TCP_threads_22', u'interval': 1, u'threads': 22, u'time': 30, u'csv': True, u'class': u'iperf_graph'}}, u'agents': {u'a-002': {u'ip': u'192.168.171.4', u'master_id': u'a-001', u'master': {u'ip': u'192.168.171.2', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, u'id': u'a-002', u'mode': u'slave'}, u'a-001': {u'ip': u'192.168.171.2', u'slave_id': u'a-002', u'slave': {u'ip': u'192.168.171.4', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}, u'id': u'a-001', u'mode': u'master'}}, u'sla': []},
#     ("tun", True, False, True, "instances"): {u'scenarios': {u'OpenStack L2 Performance': {u'file_name': u'/usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml', u'deployment': {u'agents': [{u'ip': u'192.168.170.4', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, {u'ip': u'192.168.170.3', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}]}, u'execution': {u'tests': [{u'time': 30, u'threads': 22, u'class': u'iperf_graph', u'title': u'TCP_threads_22'}]}, u'description': u'This scenario tests network between different compute nodes.', u'title': u'OpenStack L2 Performance'}}, u'records': {u'39d69d5a-66a5-4394-a039-f25772c29dcd': {u'stats': {u'bandwidth': {u'max': 18364.0, u'min': 17887.0, u'unit': u'Mbit/s', u'mean': 17927.827586206895}}, u'scenario': u'OpenStack L2 Performance', u'concurrency': 1, u'test': u'TCP_threads_22', u'x-chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 18364.0, 17929.0, 17914.0, 17908.0, 17915.0, 17895.0, 17920.0, 17888.0, 17918.0, 17936.0, 17887.0, 17909.0, 17932.0, 17907.0, 17919.0, 17921.0, 17900.0, 17912.0, 17921.0, 17915.0, 17924.0, 17895.0, 17892.0, 17896.0, 17917.0, 17946.0, 17897.0, 17899.0, 17931.0]], u'type': u'concurrency', u'id': u'39d69d5a-66a5-4394-a039-f25772c29dcd', u'node_chart': [[u'x', None], [u'Mean bandwidth', 17927.827586206895], [u'Max bandwidth', 18364.0], [u'Min bandwidth', 17887.0]]}, u'1e02682b-f0d9-4c63-b1d5-a13c5e801358': {u'test': u'TCP_threads_22', u'type': u'test', u'chart': [[u'Mean bandwidth', 17927.827586206895], [u'x', 1]], u'scenario': u'OpenStack L2 Performance', u'id': u'1e02682b-f0d9-4c63-b1d5-a13c5e801358'}, u'7e2be52c-dd35-4c27-b292-51e91f558fa7': {u'status': u'ok', u'node': None, u'finish': 1474051941.827928, u'stats': {u'bandwidth': {u'min': 17887.0, u'max': 18364.0, u'median': 17915.0, u'stdev': 84.714123726, u'unit': u'Mbit/s', u'mean': 17927.827586206895}}, u'concurrency': 1, u'scenario': u'OpenStack L2 Performance', u'schedule': 1474051911.780466, u'chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 18364.0, 17929.0, 17914.0, 17908.0, 17915.0, 17895.0, 17920.0, 17888.0, 17918.0, 17936.0, 17887.0, 17909.0, 17932.0, 17907.0, 17919.0, 17921.0, 17900.0, 17912.0, 17921.0, 17915.0, 17924.0, 17895.0, 17892.0, 17896.0, 17917.0, 17946.0, 17897.0, 17899.0, 17931.0]], u'agent': u'a-001', u'id': u'7e2be52c-dd35-4c27-b292-51e91f558fa7', u'start': 1474051911.790635, u'meta': [[u'time', u's'], [u'bandwidth', u'Mbit/s']], u'command': {u'type': u'program', u'data': u'iperf --client 192.168.170.3 --format m --time 30 --parallel 22 --interval 1 --nodelay --reportstyle C'}, u'samples': [[1.0, 18364.0], [2.0, 17929.0], [3.0, 17914.0], [4.0, 17908.0], [5.0, 17915.0], [6.0, 17895.0], [7.0, 17920.0], [8.0, 17888.0], [9.0, 17918.0], [10.0, 17936.0], [11.0, 17887.0], [12.0, 17909.0], [13.0, 17932.0], [14.0, 17907.0], [15.0, 17919.0], [16.0, 17921.0], [17.0, 17900.0], [18.0, 17912.0], [19.0, 17921.0], [20.0, 17915.0], [21.0, 17924.0], [22.0, 17895.0], [23.0, 17892.0], [24.0, 17896.0], [25.0, 17917.0], [26.0, 17946.0], [27.0, 17897.0], [28.0, 17899.0], [29.0, 17931.0]], u'executor': u'iperf_graph', u'test': u'TCP_threads_22', u'type': u'agent', u'stderr': u''}}, u'tests': {u'TCP_threads_22': {u'title': u'TCP_threads_22', u'interval': 1, u'threads': 22, u'time': 30, u'csv': True, u'class': u'iperf_graph'}}, u'agents': {u'a-002': {u'ip': u'192.168.170.3', u'master_id': u'a-001', u'master': {u'ip': u'192.168.170.4', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, u'id': u'a-002', u'mode': u'slave'}, u'a-001': {u'ip': u'192.168.170.4', u'slave_id': u'a-002', u'slave': {u'ip': u'192.168.170.3', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}, u'id': u'a-001', u'mode': u'master'}}, u'sla': []},
#     ("vlan", True, False, True, "instances"): {u'scenarios': {u'OpenStack L2 Performance': {u'file_name': u'/usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml', u'deployment': {u'agents': [{u'ip': u'192.168.171.2', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, {u'ip': u'192.168.171.5', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}]}, u'execution': {u'tests': [{u'time': 30, u'threads': 22, u'class': u'iperf_graph', u'title': u'TCP_threads_22'}]}, u'description': u'This scenario tests network between different compute nodes.', u'title': u'OpenStack L2 Performance'}}, u'records': {u'bd868042-f1bb-434e-886a-3735dfe85ebf': {u'stats': {u'bandwidth': {u'max': 18345.0, u'min': 17875.0, u'unit': u'Mbit/s', u'mean': 17927.344827586207}}, u'scenario': u'OpenStack L2 Performance', u'concurrency': 1, u'test': u'TCP_threads_22', u'x-chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 18345.0, 17919.0, 17918.0, 17888.0, 17935.0, 17924.0, 17897.0, 17905.0, 17914.0, 17913.0, 17882.0, 17935.0, 17910.0, 17939.0, 17875.0, 17914.0, 17909.0, 17906.0, 17909.0, 17916.0, 17906.0, 17959.0, 17885.0, 17946.0, 17913.0, 17890.0, 17932.0, 17879.0, 17930.0]], u'type': u'concurrency', u'id': u'bd868042-f1bb-434e-886a-3735dfe85ebf', u'node_chart': [[u'x', None], [u'Mean bandwidth', 17927.344827586207], [u'Max bandwidth', 18345.0], [u'Min bandwidth', 17875.0]]}, u'1e8c61c4-2743-4fde-8f86-f0fbe93ce21b': {u'status': u'ok', u'node': None, u'finish': 1474056161.566532, u'stats': {u'bandwidth': {u'min': 17875.0, u'max': 18345.0, u'median': 17913.0, u'stdev': 82.686362133, u'unit': u'Mbit/s', u'mean': 17927.344827586207}}, u'concurrency': 1, u'scenario': u'OpenStack L2 Performance', u'schedule': 1474056131.520112, u'chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 18345.0, 17919.0, 17918.0, 17888.0, 17935.0, 17924.0, 17897.0, 17905.0, 17914.0, 17913.0, 17882.0, 17935.0, 17910.0, 17939.0, 17875.0, 17914.0, 17909.0, 17906.0, 17909.0, 17916.0, 17906.0, 17959.0, 17885.0, 17946.0, 17913.0, 17890.0, 17932.0, 17879.0, 17930.0]], u'agent': u'a-001', u'id': u'1e8c61c4-2743-4fde-8f86-f0fbe93ce21b', u'start': 1474056131.530185, u'meta': [[u'time', u's'], [u'bandwidth', u'Mbit/s']], u'command': {u'type': u'program', u'data': u'iperf --client 192.168.171.5 --format m --time 30 --parallel 22 --interval 1 --nodelay --reportstyle C'}, u'samples': [[1.0, 18345.0], [2.0, 17919.0], [3.0, 17918.0], [4.0, 17888.0], [5.0, 17935.0], [6.0, 17924.0], [7.0, 17897.0], [8.0, 17905.0], [9.0, 17914.0], [10.0, 17913.0], [11.0, 17882.0], [12.0, 17935.0], [13.0, 17910.0], [14.0, 17939.0], [15.0, 17875.0], [16.0, 17914.0], [17.0, 17909.0], [18.0, 17906.0], [19.0, 17909.0], [20.0, 17916.0], [21.0, 17906.0], [22.0, 17959.0], [23.0, 17885.0], [24.0, 17946.0], [25.0, 17913.0], [26.0, 17890.0], [27.0, 17932.0], [28.0, 17879.0], [29.0, 17930.0]], u'executor': u'iperf_graph', u'test': u'TCP_threads_22', u'type': u'agent', u'stderr': u''}, u'9181fab1-43b7-42cf-a109-a207f88c2845': {u'test': u'TCP_threads_22', u'type': u'test', u'chart': [[u'Mean bandwidth', 17927.344827586207], [u'x', 1]], u'scenario': u'OpenStack L2 Performance', u'id': u'9181fab1-43b7-42cf-a109-a207f88c2845'}}, u'tests': {u'TCP_threads_22': {u'title': u'TCP_threads_22', u'interval': 1, u'threads': 22, u'time': 30, u'csv': True, u'class': u'iperf_graph'}}, u'agents': {u'a-002': {u'ip': u'192.168.171.5', u'master_id': u'a-001', u'master': {u'ip': u'192.168.171.2', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, u'id': u'a-002', u'mode': u'slave'}, u'a-001': {u'ip': u'192.168.171.2', u'slave_id': u'a-002', u'slave': {u'ip': u'192.168.171.5', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}, u'id': u'a-001', u'mode': u'master'}}, u'sla': []},
#     ("tun", False, True, True, "instances"): {u'scenarios': {u'OpenStack L2 Performance': {u'file_name': u'/usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml', u'deployment': {u'agents': [{u'ip': u'192.168.170.3', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, {u'ip': u'192.168.170.5', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}]}, u'execution': {u'tests': [{u'time': 30, u'threads': 22, u'class': u'iperf_graph', u'title': u'TCP_threads_22'}]}, u'description': u'This scenario tests network between different compute nodes.', u'title': u'OpenStack L2 Performance'}}, u'records': {u'e6d63ccd-7ca8-43ca-9190-348b5edad379': {u'test': u'TCP_threads_22', u'type': u'test', u'chart': [[u'Mean bandwidth', 17928.41379310345], [u'x', 1]], u'scenario': u'OpenStack L2 Performance', u'id': u'e6d63ccd-7ca8-43ca-9190-348b5edad379'}, u'9705533c-f6d9-4814-a090-ebba9d1a8fb4': {u'status': u'ok', u'node': None, u'finish': 1474060874.052159, u'stats': {u'bandwidth': {u'min': 17869.0, u'max': 18374.0, u'median': 17913.0, u'stdev': 88.152493266, u'unit': u'Mbit/s', u'mean': 17928.41379310345}}, u'concurrency': 1, u'scenario': u'OpenStack L2 Performance', u'schedule': 1474060843.014553, u'chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 18374.0, 17949.0, 17893.0, 17930.0, 17919.0, 17900.0, 17935.0, 17869.0, 17949.0, 17884.0, 17923.0, 17918.0, 17950.0, 17892.0, 17874.0, 17923.0, 17930.0, 17902.0, 17899.0, 17919.0, 17929.0, 17906.0, 17913.0, 17886.0, 17912.0, 17936.0, 17907.0, 17905.0, 17898.0]], u'agent': u'a-001', u'id': u'9705533c-f6d9-4814-a090-ebba9d1a8fb4', u'start': 1474060843.024643, u'meta': [[u'time', u's'], [u'bandwidth', u'Mbit/s']], u'command': {u'type': u'program', u'data': u'iperf --client 192.168.170.5 --format m --time 30 --parallel 22 --interval 1 --nodelay --reportstyle C'}, u'samples': [[1.0, 18374.0], [2.0, 17949.0], [3.0, 17893.0], [4.0, 17930.0], [5.0, 17919.0], [6.0, 17900.0], [7.0, 17935.0], [8.0, 17869.0], [9.0, 17949.0], [10.0, 17884.0], [11.0, 17923.0], [12.0, 17918.0], [13.0, 17950.0], [14.0, 17892.0], [15.0, 17874.0], [16.0, 17923.0], [17.0, 17930.0], [18.0, 17902.0], [19.0, 17899.0], [20.0, 17919.0], [21.0, 17929.0], [22.0, 17906.0], [23.0, 17913.0], [24.0, 17886.0], [25.0, 17912.0], [26.0, 17936.0], [27.0, 17907.0], [28.0, 17905.0], [29.0, 17898.0]], u'executor': u'iperf_graph', u'test': u'TCP_threads_22', u'type': u'agent', u'stderr': u''}, u'd6fb5355-20f3-4643-8b7c-4839f18497d3': {u'stats': {u'bandwidth': {u'max': 18374.0, u'min': 17869.0, u'unit': u'Mbit/s', u'mean': 17928.41379310345}}, u'scenario': u'OpenStack L2 Performance', u'concurrency': 1, u'test': u'TCP_threads_22', u'x-chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 18374.0, 17949.0, 17893.0, 17930.0, 17919.0, 17900.0, 17935.0, 17869.0, 17949.0, 17884.0, 17923.0, 17918.0, 17950.0, 17892.0, 17874.0, 17923.0, 17930.0, 17902.0, 17899.0, 17919.0, 17929.0, 17906.0, 17913.0, 17886.0, 17912.0, 17936.0, 17907.0, 17905.0, 17898.0]], u'type': u'concurrency', u'id': u'd6fb5355-20f3-4643-8b7c-4839f18497d3', u'node_chart': [[u'x', None], [u'Mean bandwidth', 17928.41379310345], [u'Max bandwidth', 18374.0], [u'Min bandwidth', 17869.0]]}}, u'tests': {u'TCP_threads_22': {u'title': u'TCP_threads_22', u'interval': 1, u'threads': 22, u'time': 30, u'csv': True, u'class': u'iperf_graph'}}, u'agents': {u'a-002': {u'ip': u'192.168.170.5', u'master_id': u'a-001', u'master': {u'ip': u'192.168.170.3', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, u'id': u'a-002', u'mode': u'slave'}, u'a-001': {u'ip': u'192.168.170.3', u'slave_id': u'a-002', u'slave': {u'ip': u'192.168.170.5', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}, u'id': u'a-001', u'mode': u'master'}}, u'sla': []},
#     ("tun", False, True, True, "nodes"): {u'scenarios': {u'OpenStack L2 Performance': {u'file_name': u'/usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/VMs.yaml', u'deployment': {u'accommodation': [u'pair', u'single_room', {u'compute_nodes': 2}], u'template': u'l2.hot'}, u'execution': {u'tests': [{u'time': 10, u'threads': 8, u'class': u'iperf_graph', u'title': u'TCP_threads_8'}]}, u'description': u'This scenario run test between 2 VMs on separate nodes', u'title': u'OpenStack L2 Performance'}}, u'records': {u'55852542-3920-4c94-b51c-53993eb0be91': {u'stats': {}, u'scenario': u'OpenStack L2 Performance', u'concurrency': 1, u'test': u'TCP_threads_8', u'x-chart': [], u'type': u'concurrency', u'id': u'55852542-3920-4c94-b51c-53993eb0be91', u'node_chart': [[u'x', u'node-4.test.domain.local']]}, u'cbef22df-0c21-4e88-a7e2-bf4bd630b12a': {u'status': u'error', u'info': u'Empty result from iperf', u'finish': 1474061029.676303, u'node': u'node-4.test.domain.local', u'stderr': u'connect failed: Connection refused\nconnect failed: Connection refused\nconnect failed: Connection refused\nconnect failed: Connection refused\nconnect failed: Connection refused\nconnect failed: Connection refused\nconnect failed: Connection refused\nconnect failed: Connection refused\n', u'scenario': u'OpenStack L2 Performance', u'schedule': 1474061029.650075, u'traceback': u'Traceback (most recent call last):\n File "/usr/local/lib/python2.7/dist-packages/shaker/engine/quorum.py", line 97, in process_reply\n reply = self.executors[agent_id].process_reply(message)\n File "/usr/local/lib/python2.7/dist-packages/shaker/engine/executors/iperf.py", line 64, in process_reply\n raise base.ExecutorException(result, \'Empty result from iperf\')\nExecutorException: Empty result from iperf\n', u'chart': [], u'agent': u'shaker_skadrf_master_0', u'start': 1474061029.668206, u'command': {u'type': u'program', u'data': u'iperf --client 10.0.0.4 --format m --time 10 --parallel 8 --interval 1 --nodelay --reportstyle C'}, u'concurrency': 1, u'executor': u'iperf_graph', u'test': u'TCP_threads_8', u'stats': {}, u'type': u'agent', u'id': u'cbef22df-0c21-4e88-a7e2-bf4bd630b12a'}, u'77bbced8-6995-4324-8843-36bbe71911b0': {u'test': u'TCP_threads_8', u'type': u'test', u'chart': [[u'x', 1]], u'scenario': u'OpenStack L2 Performance', u'id': u'77bbced8-6995-4324-8843-36bbe71911b0'}}, u'tests': {u'TCP_threads_8': {u'title': u'TCP_threads_8', u'interval': 1, u'threads': 8, u'time': 10, u'csv': True, u'class': u'iperf_graph'}}, u'agents': {u'shaker_skadrf_master_0': {u'node': u'node-4.test.domain.local', u'slave': {u'node': u'node-3.test.domain.local', u'zone': u'nova', u'availability_zone': u'nova:node-3.test.domain.local', u'ip': u'10.0.0.4', u'mode': u'slave', u'master_id': u'shaker_skadrf_master_0', u'id': u'shaker_skadrf_slave_0'}, u'zone': u'nova', u'availability_zone': u'nova:node-4.test.domain.local', u'ip': u'10.0.0.5', u'mode': u'master', u'slave_id': u'shaker_skadrf_slave_0', u'id': u'shaker_skadrf_master_0'}, u'shaker_skadrf_slave_0': {u'node': u'node-3.test.domain.local', u'zone': u'nova', u'availability_zone': u'nova:node-3.test.domain.local', u'ip': u'10.0.0.4', u'master': {u'node': u'node-4.test.domain.local', u'zone': u'nova', u'availability_zone': u'nova:node-4.test.domain.local', u'ip': u'10.0.0.5', u'mode': u'master', u'slave_id': u'shaker_skadrf_slave_0', u'id': u'shaker_skadrf_master_0'}, u'mode': u'slave', u'master_id': u'shaker_skadrf_master_0', u'id': u'shaker_skadrf_slave_0'}}, u'sla': []},
#     ("vlan", False, True, True, "instances"): {u'scenarios': {u'OpenStack L2 Performance': {u'file_name': u'/usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/nodes.yaml', u'deployment': {u'agents': [{u'ip': u'192.168.171.3', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, {u'ip': u'192.168.171.5', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}]}, u'execution': {u'tests': [{u'time': 30, u'threads': 22, u'class': u'iperf_graph', u'title': u'TCP_threads_22'}]}, u'description': u'This scenario tests network between different compute nodes.', u'title': u'OpenStack L2 Performance'}}, u'records': {u'd5883b93-c790-4461-b791-b35394e9b5e2': {u'stats': {u'bandwidth': {u'max': 18299.0, u'min': 17879.0, u'unit': u'Mbit/s', u'mean': 17925.827586206895}}, u'scenario': u'OpenStack L2 Performance', u'concurrency': 1, u'test': u'TCP_threads_22', u'x-chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 18299.0, 17934.0, 17916.0, 17913.0, 17906.0, 17934.0, 17885.0, 17915.0, 17923.0, 17901.0, 17928.0, 17904.0, 17894.0, 17960.0, 17879.0, 17916.0, 17923.0, 17891.0, 17943.0, 17904.0, 17929.0, 17894.0, 17903.0, 17904.0, 17916.0, 17899.0, 17923.0, 17904.0, 17909.0]], u'type': u'concurrency', u'id': u'd5883b93-c790-4461-b791-b35394e9b5e2', u'node_chart': [[u'x', None], [u'Mean bandwidth', 17925.827586206895], [u'Max bandwidth', 18299.0], [u'Min bandwidth', 17879.0]]}, u'6463ee11-97eb-45ee-871d-93ee17e86779': {u'status': u'ok', u'node': None, u'finish': 1474065479.307011, u'stats': {u'bandwidth': {u'min': 17879.0, u'max': 18299.0, u'median': 17913.0, u'stdev': 73.759628244, u'unit': u'Mbit/s', u'mean': 17925.827586206895}}, u'concurrency': 1, u'scenario': u'OpenStack L2 Performance', u'schedule': 1474065449.258548, u'chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0], [u'bandwidth', 18299.0, 17934.0, 17916.0, 17913.0, 17906.0, 17934.0, 17885.0, 17915.0, 17923.0, 17901.0, 17928.0, 17904.0, 17894.0, 17960.0, 17879.0, 17916.0, 17923.0, 17891.0, 17943.0, 17904.0, 17929.0, 17894.0, 17903.0, 17904.0, 17916.0, 17899.0, 17923.0, 17904.0, 17909.0]], u'agent': u'a-001', u'id': u'6463ee11-97eb-45ee-871d-93ee17e86779', u'start': 1474065449.268667, u'meta': [[u'time', u's'], [u'bandwidth', u'Mbit/s']], u'command': {u'type': u'program', u'data': u'iperf --client 192.168.171.5 --format m --time 30 --parallel 22 --interval 1 --nodelay --reportstyle C'}, u'samples': [[1.0, 18299.0], [2.0, 17934.0], [3.0, 17916.0], [4.0, 17913.0], [5.0, 17906.0], [6.0, 17934.0], [7.0, 17885.0], [8.0, 17915.0], [9.0, 17923.0], [10.0, 17901.0], [11.0, 17928.0], [12.0, 17904.0], [13.0, 17894.0], [14.0, 17960.0], [15.0, 17879.0], [16.0, 17916.0], [17.0, 17923.0], [18.0, 17891.0], [19.0, 17943.0], [20.0, 17904.0], [21.0, 17929.0], [22.0, 17894.0], [23.0, 17903.0], [24.0, 17904.0], [25.0, 17916.0], [26.0, 17899.0], [27.0, 17923.0], [28.0, 17904.0], [29.0, 17909.0]], u'executor': u'iperf_graph', u'test': u'TCP_threads_22', u'type': u'agent', u'stderr': u''}, u'b09437ec-f047-4fa6-a51b-be851b16b511': {u'test': u'TCP_threads_22', u'type': u'test', u'chart': [[u'Mean bandwidth', 17925.827586206895], [u'x', 1]], u'scenario': u'OpenStack L2 Performance', u'id': u'b09437ec-f047-4fa6-a51b-be851b16b511'}}, u'tests': {u'TCP_threads_22': {u'title': u'TCP_threads_22', u'interval': 1, u'threads': 22, u'time': 30, u'csv': True, u'class': u'iperf_graph'}}, u'agents': {u'a-002': {u'ip': u'192.168.171.5', u'master_id': u'a-001', u'master': {u'ip': u'192.168.171.3', u'slave_id': u'a-002', u'id': u'a-001', u'mode': u'master'}, u'id': u'a-002', u'mode': u'slave'}, u'a-001': {u'ip': u'192.168.171.3', u'slave_id': u'a-002', u'slave': {u'ip': u'192.168.171.5', u'master_id': u'a-001', u'id': u'a-002', u'mode': u'slave'}, u'id': u'a-001', u'mode': u'master'}}, u'sla': []},
#     ("vlan", False, True, True, "nodes"): {u'scenarios': {u'OpenStack L2 Performance': {u'file_name': u'/usr/local/lib/python2.7/dist-packages/shaker/scenarios/openstack/VMs.yaml', u'deployment': {u'accommodation': [u'pair', u'single_room', {u'compute_nodes': 2}], u'template': u'l2.hot'}, u'execution': {u'tests': [{u'time': 10, u'threads': 8, u'class': u'iperf_graph', u'title': u'TCP_threads_8'}]}, u'description': u'This scenario run test between 2 VMs on separate nodes', u'title': u'OpenStack L2 Performance'}}, u'records': {u'079c75b2-08eb-441b-96db-8438d82a13e3': {u'test': u'TCP_threads_8', u'type': u'test', u'chart': [[u'Mean bandwidth', 11138.888888888889], [u'x', 1]], u'scenario': u'OpenStack L2 Performance', u'id': u'079c75b2-08eb-441b-96db-8438d82a13e3'}, u'6633836c-7038-4453-8893-ec9ce13a1b40': {u'stats': {u'bandwidth': {u'max': 11714.0, u'min': 10447.0, u'unit': u'Mbit/s', u'mean': 11138.888888888889}}, u'scenario': u'OpenStack L2 Performance', u'concurrency': 1, u'test': u'TCP_threads_8', u'x-chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0], [u'bandwidth', 11670.0, 11399.0, 11405.0, 11058.0, 11714.0, 10496.0, 10447.0, 11453.0, 10608.0]], u'type': u'concurrency', u'id': u'6633836c-7038-4453-8893-ec9ce13a1b40', u'node_chart': [[u'x', u'node-2.test.domain.local'], [u'Mean bandwidth', 11138.888888888889], [u'Max bandwidth', 11714.0], [u'Min bandwidth', 10447.0]]}, u'6b2348a6-5534-40e9-b1ce-67a7dba41b97': {u'status': u'ok', u'node': u'node-2.test.domain.local', u'finish': 1474065639.120168, u'stats': {u'bandwidth': {u'min': 10447.0, u'max': 11714.0, u'median': 11399.0, u'stdev': 541.53003405, u'unit': u'Mbit/s', u'mean': 11138.888888888889}}, u'concurrency': 1, u'scenario': u'OpenStack L2 Performance', u'schedule': 1474065629.073363, u'chart': [[u'time', 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0], [u'bandwidth', 11670.0, 11399.0, 11405.0, 11058.0, 11714.0, 10496.0, 10447.0, 11453.0, 10608.0]], u'agent': u'shaker_pdtriz_master_0', u'id': u'6b2348a6-5534-40e9-b1ce-67a7dba41b97', u'start': 1474065629.084144, u'meta': [[u'time', u's'], [u'bandwidth', u'Mbit/s']], u'command': {u'type': u'program', u'data': u'iperf --client 10.0.0.4 --format m --time 10 --parallel 8 --interval 1 --nodelay --reportstyle C'}, u'samples': [[1.0, 11670.0], [2.0, 11399.0], [3.0, 11405.0], [4.0, 11058.0], [5.0, 11714.0], [6.0, 10496.0], [7.0, 10447.0], [8.0, 11453.0], [9.0, 10608.0]], u'executor': u'iperf_graph', u'test': u'TCP_threads_8', u'type': u'agent', u'stderr': u''}}, u'tests': {u'TCP_threads_8': {u'title': u'TCP_threads_8', u'interval': 1, u'threads': 8, u'time': 10, u'csv': True, u'class': u'iperf_graph'}}, u'agents': {u'shaker_pdtriz_slave_0': {u'node': u'node-4.test.domain.local', u'zone': u'nova', u'availability_zone': u'nova:node-4.test.domain.local', u'ip': u'10.0.0.4', u'master': {u'node': u'node-2.test.domain.local', u'zone': u'nova', u'availability_zone': u'nova:node-2.test.domain.local', u'ip': u'10.0.0.5', u'mode': u'master', u'slave_id': u'shaker_pdtriz_slave_0', u'id': u'shaker_pdtriz_master_0'}, u'mode': u'slave', u'master_id': u'shaker_pdtriz_master_0', u'id': u'shaker_pdtriz_slave_0'}, u'shaker_pdtriz_master_0': {u'node': u'node-2.test.domain.local', u'slave': {u'node': u'node-4.test.domain.local', u'zone': u'nova', u'availability_zone': u'nova:node-4.test.domain.local', u'ip': u'10.0.0.4', u'mode': u'slave', u'master_id': u'shaker_pdtriz_master_0', u'id': u'shaker_pdtriz_slave_0'}, u'zone': u'nova', u'availability_zone': u'nova:node-2.test.domain.local', u'ip': u'10.0.0.5', u'mode': u'master', u'slave_id': u'shaker_pdtriz_slave_0', u'id': u'shaker_pdtriz_master_0'}}, u'sla': []}
# }
#
# reporter = ShakerTestResultReporter(data)
#reporter.send_report()

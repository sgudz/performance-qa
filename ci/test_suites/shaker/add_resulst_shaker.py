import ConfigParser
import base64
import json
import urllib2
import re
import os
try:
    from BeautifulSoup import BeautifulSoup
except ImportError:
    from bs4 import BeautifulSoup

# Testrail API
class APIClient:
    def __init__(self, base_url):
        self.user = ''
        self.password = ''
        if not base_url.endswith('/'):
            base_url += '/'
        self.__url = base_url + 'index.php?/api/v2/'

    def send_get(self, uri):
        return self.__send_request('GET', uri, None)

    def send_post(self, uri, data):
        return self.__send_request('POST', uri, data)

    def __send_request(self, method, uri, data):
        url = self.__url + uri
        request = urllib2.Request(url)
        if (method == 'POST'):
            request.add_data(json.dumps(data))
        auth = base64.b64encode('%s:%s' % (self.user, self.password))
        request.add_header('Authorization', 'Basic %s' % auth)
        request.add_header('Content-Type', 'application/json')

        e = None
        try:
            response = urllib2.urlopen(request).read()
        except urllib2.HTTPError as e:
            response = e.read()

        if response:
            result = json.loads(response)
        else:
            result = {}

        if e != None:
            if result and 'error' in result:
                error = '"' + result['error'] + '"'
            else:
                error = 'No additional error message received'
            raise APIError('TestRail API returned HTTP %s (%s)' %
                           (e.code, error))

        return result


class APIError(Exception):
    pass


client = APIClient('https://mirantis.testrail.com/')
client.user = 'performance-qa@mirantis.com'
client.password = '1qaz@WSX'

### Parsing env.conf file for required data
parser = ConfigParser.SafeConfigParser()
parser.read('/root/env.cfg')
run_id = dict(parser.items('testrail'))['run_id']
suite_id = dict(parser.items('testrail'))['suite_id']
fuel_ip = dict(parser.items('fuel'))['fuel_ip']
version = str(dict(parser.items('testrail'))['version'])
run_name = str(dict(parser.items('testrail'))['run_name'])
create_new_run = str(dict(parser.items('testrail'))['create_new_run']) 

project_id = 3
project_runs = client.send_get('get_runs/{}'.format(project_id))

if create_new_run == "true":
    if run_name not in [item['name'] for item in project_runs]:
        data_str = """{"suite_id": %(suite_id)s, "name": "%(name)s", "assignedto_id": 24, "include_all": true}""" %{"suite_id": suite_id, "name": run_name}
        data = json.loads(data_str)
        result = client.send_post('add_run/3', data)
        run_id = result['id']
    else:
        run_id = [our['id'] for our in project_runs if our['name'] == run_name][0]
        print "Run exists. Run ID is: {}".format(run_id)
else:
    run_id = dict(parser.items('testrail'))['run_id']

def get_tests_ids():
    tests = client.send_get('get_tests/{}'.format(run_id))
    test_names = {}
    for item in tests:
        test_names[item['title']] = item['id']
    return test_names

test_off_dvr_vxlan_inst = test_off_dvr_vlan_inst = test_on_dvr_vxlan_inst = test_on_dvr_vlan_inst = test_on_l3ha_vxlan_nodes = test_on_l3ha_vxlan_inst = test_on_l3ha_vlan_nodes = test_on_l3ha_vlan_inst = None
list_t = get_tests_ids()
for item in list_t.keys():
    if "Neutron VxLAN Instance-to-Instance; bonding: on; Ubuntu" in item:
        test_off_dvr_vxlan_inst = list_t[item]
    elif "Neutron VLAN Instance-to-Instance; bonding: on; Ubuntu" in item:
        test_off_dvr_vlan_inst = list_t[item]
    elif "Neutron VxLAN Instance-to-Instance; DVR on, bonding: on; Ubuntu" in item:
        test_on_dvr_vxlan_inst = list_t[item]
    elif "Neutron VLAN Instance-to-Instance; DVR on, bonding: on; Ubuntu" in item:
        test_on_dvr_vlan_inst = list_t[item]
    elif "Neutron VxLAN Node-to-Node; L3 HA on, bonding: on; Ubuntu" in item:
        test_on_l3ha_vxlan_nodes = list_t[item]
    elif "Neutron VxLAN Instance-to-Instance; L3 HA on, bonding: on; Ubuntu" in item:
        test_on_l3ha_vxlan_inst = list_t[item]
    elif "Neutron VLAN Node-to-Node; L3 HA on, bonding: on; Ubuntu" in item:
        test_on_l3ha_vlan_nodes = list_t[item]
    elif "Neutron VLAN Instance-to-Instance; L3 HA on, bonding: on; Ubuntu" in item:
        test_on_l3ha_vlan_inst = list_t[item]

## Define baseline data from TestRail
base_off_dvr_vxlan_inst_median = client.send_get('get_test/{}'.format(test_off_dvr_vxlan_inst))['custom_test_case_steps'][0]['expected']
base_off_dvr_vxlan_inst_stdev = client.send_get('get_test/{}'.format(test_off_dvr_vxlan_inst))['custom_test_case_steps'][1]['expected']
base_off_dvr_vlan_inst_median = client.send_get('get_test/{}'.format(test_off_dvr_vlan_inst))['custom_test_case_steps'][0]['expected']
base_off_dvr_vlan_inst_stdev = client.send_get('get_test/{}'.format(test_off_dvr_vlan_inst))['custom_test_case_steps'][1]['expected']
base_on_dvr_vxlan_inst_median = client.send_get('get_test/{}'.format(test_on_dvr_vxlan_inst))['custom_test_case_steps'][0]['expected']
base_on_dvr_vxlan_inst_stdev = client.send_get('get_test/{}'.format(test_on_dvr_vxlan_inst))['custom_test_case_steps'][1]['expected']
base_on_dvr_vlan_inst_median = client.send_get('get_test/{}'.format(test_on_dvr_vlan_inst))['custom_test_case_steps'][0]['expected']
base_on_dvr_vlan_inst_stdev = client.send_get('get_test/{}'.format(test_on_dvr_vlan_inst))['custom_test_case_steps'][1]['expected']

base_on_l3ha_vxlan_nodes_median = client.send_get('get_test/{}'.format(test_on_l3ha_vxlan_nodes))['custom_test_case_steps'][0]['expected']
base_on_l3ha_vxlan_nodes_stdev = client.send_get('get_test/{}'.format(test_on_l3ha_vxlan_nodes))['custom_test_case_steps'][1]['expected']
base_on_l3ha_vxlan_inst_median = client.send_get('get_test/{}'.format(test_on_l3ha_vxlan_inst))['custom_test_case_steps'][0]['expected']
base_on_l3ha_vxlan_inst_stdev = client.send_get('get_test/{}'.format(test_on_l3ha_vxlan_inst))['custom_test_case_steps'][1]['expected']
base_on_l3ha_vlan_nodes_median = client.send_get('get_test/{}'.format(test_on_l3ha_vlan_nodes))['custom_test_case_steps'][0]['expected']
base_on_l3ha_vlan_nodes_stdev = client.send_get('get_test/{}'.format(test_on_l3ha_vlan_nodes))['custom_test_case_steps'][1]['expected']
base_on_l3ha_vlan_inst_median = client.send_get('get_test/{}'.format(test_on_l3ha_vlan_inst))['custom_test_case_steps'][0]['expected']
base_on_l3ha_vlan_inst_stdev = client.send_get('get_test/{}'.format(test_on_l3ha_vlan_inst))['custom_test_case_steps'][1]['expected']


## Actual data
parser2 = ConfigParser.SafeConfigParser()
parser2.read('/root/var_to_export')


off_dvr_vxlan_inst_median = dict(parser2.items('testrail_results'))['off_dvr_vxlan_inst_median']
off_dvr_vxlan_inst_stdev = dict(parser2.items('testrail_results'))['off_dvr_vxlan_inst_stdev']
off_dvr_vlan_inst_median = dict(parser2.items('testrail_results'))['off_dvr_vlan_inst_median']
off_dvr_vlan_inst_stdev = dict(parser2.items('testrail_results'))['off_dvr_vlan_inst_stdev']
on_dvr_vxlan_inst_median = dict(parser2.items('testrail_results'))['on_dvr_vxlan_inst_median']
on_dvr_vxlan_inst_stdev = dict(parser2.items('testrail_results'))['on_dvr_vxlan_inst_stdev']
on_dvr_vlan_inst_median = dict(parser2.items('testrail_results'))['on_dvr_vlan_inst_median']
on_dvr_vlan_inst_stdev = dict(parser2.items('testrail_results'))['on_dvr_vlan_inst_stdev']

on_l3ha_vxlan_nodes_median = dict(parser2.items('testrail_results'))['on_l3ha_vxlan_nodes_median']
on_l3ha_vxlan_nodes_stdev = dict(parser2.items('testrail_results'))['on_l3ha_vxlan_nodes_stdev']
on_l3ha_vxlan_inst_median = dict(parser2.items('testrail_results'))['on_l3ha_vxlan_inst_median']
on_l3ha_vxlan_inst_stdev = dict(parser2.items('testrail_results'))['on_l3ha_vxlan_inst_stdev']
on_l3ha_vlan_nodes_median = dict(parser2.items('testrail_results'))['on_l3ha_vlan_nodes_median']
on_l3ha_vlan_nodes_stdev = dict(parser2.items('testrail_results'))['on_l3ha_vlan_nodes_stdev']
on_l3ha_vlan_inst_median = dict(parser2.items('testrail_results'))['on_l3ha_vlan_inst_median']
on_l3ha_vlan_inst_stdev = dict(parser2.items('testrail_results'))['on_l3ha_vlan_inst_stdev']

### Default status
off_dvr_vxlan_inst_glob_status = off_dvr_vxlan_inst_custom_status = 1
off_dvr_vlan_inst_glob_status = off_dvr_vlan_inst_custom_status = 1
on_dvr_vxlan_inst_glob_status = on_dvr_vxlan_inst_custom_status = 1
on_dvr_vlan_inst_glob_status = on_dvr_vlan_inst_custom_status = 1

on_l3ha_vxlan_nodes_glob_status = on_l3ha_vxlan_nodes_custom_status = 1
on_l3ha_vxlan_inst_glob_status = on_l3ha_vxlan_inst_custom_status = 1
on_l3ha_vlan_nodes_glob_status = on_l3ha_vlan_nodes_custom_status = 1
on_l3ha_vlan_inst_glob_status = on_l3ha_vlan_inst_custom_status = 1

### Define status for tests, based on Baseline - 20%
if off_dvr_vxlan_inst_median < float(base_off_dvr_vxlan_inst_median) * 0.8:
    off_dvr_vxlan_inst_glob_status = off_dvr_vxlan_inst_custom_status = 5
if off_dvr_vlan_inst_median < float(base_off_dvr_vlan_inst_median) * 0.8:
    off_dvr_vlan_inst_glob_status = off_dvr_vlan_inst_custom_status = 5
if on_dvr_vxlan_inst_median < float(base_on_dvr_vxlan_inst_median) * 0.8:
    on_dvr_vxlan_inst_glob_status = on_dvr_vxlan_inst_custom_status = 5
if on_dvr_vlan_inst_median < float(base_on_dvr_vlan_inst_median) * 0.8:
    on_dvr_vlan_inst_glob_status = on_dvr_vlan_inst_custom_status = 5

if on_l3ha_vxlan_nodes_median < float(base_on_l3ha_vxlan_nodes_median) * 0.8:
    on_l3ha_vxlan_nodes_glob_status = on_l3ha_vxlan_nodes_custom_status = 5
if on_l3ha_vxlan_inst_median < float(base_on_l3ha_vxlan_inst_median) * 0.8:
    on_l3ha_vxlan_inst_glob_status = on_l3ha_vxlan_inst_custom_status = 5
if on_l3ha_vlan_nodes_median < float(base_on_l3ha_vlan_nodes_median) * 0.8:
    on_l3ha_vlan_nodes_glob_status = on_l3ha_vlan_nodes_custom_status = 5
if on_l3ha_vlan_inst_median < float(base_on_l3ha_vlan_inst_median) * 0.8:
    on_l3ha_vlan_inst_glob_status = on_l3ha_vlan_inst_custom_status = 5

### Custom results for tests
custom_res_off_dvr_vxlan_inst = [{'status_id': off_dvr_vxlan_inst_custom_status, 'content': 'Check [network bandwidth, Median; Mbps]',
                         'expected': str(base_off_dvr_vxlan_inst_median),
			 'actual': str(off_dvr_vxlan_inst_median)},
                        {'status_id': 1, 'content': 'Check [deviation; pcs]', 'expected': str(base_off_dvr_vxlan_inst_stdev),
                         'actual': str(off_dvr_vxlan_inst_stdev)}]

custom_res_off_dvr_vlan_inst = [{'status_id': off_dvr_vlan_inst_custom_status, 'content': 'Check [network bandwidth, Median; Mbps]',
                        'expected': str(base_off_dvr_vlan_inst_median),
                         'actual': str(off_dvr_vlan_inst_median)},
                        {'status_id': 1, 'content': 'Check [deviation; pcs]', 'expected': str(base_off_dvr_vlan_inst_stdev),
                         'actual': str(off_dvr_vlan_inst_stdev)}]

custom_res_on_dvr_vxlan_inst = [{'status_id': on_dvr_vxlan_inst_custom_status, 'content': 'Check [network bandwidth, Median; Mbps]',
                         'expected': str(base_on_dvr_vxlan_inst_median),
                         'actual': str(on_dvr_vxlan_inst_median)},
                        {'status_id': 1, 'content': 'Check [deviation; pcs]', 'expected': str(base_on_dvr_vxlan_inst_stdev),
                         'actual': str(on_dvr_vxlan_inst_stdev)}]

custom_res_on_dvr_vlan_inst = [{'status_id': on_dvr_vlan_inst_custom_status, 'content': 'Check [network bandwidth, Median; Mbps]',
                         'expected': str(base_on_dvr_vlan_inst_median),
                         'actual': str(on_dvr_vlan_inst_median)},
                        {'status_id': 1, 'content': 'Check [deviation; pcs]', 'expected': str(base_on_dvr_vlan_inst_stdev),
                         'actual': str(on_dvr_vlan_inst_stdev)}]

custom_res_on_l3ha_vxlan_nodes = [{'status_id': on_l3ha_vxlan_nodes_custom_status, 'content': 'Check [network bandwidth, Median; Mbps]',
                        'expected': str(base_on_l3ha_vxlan_nodes_median),
                         'actual': str(on_l3ha_vxlan_nodes_median)},
                        {'status_id': 1, 'content': 'Check [deviation; pcs]', 'expected': str(base_on_l3ha_vxlan_nodes_stdev),
                         'actual': str(on_l3ha_vxlan_nodes_stdev)}]

custom_res_on_l3ha_vxlan_inst = [{'status_id': on_l3ha_vxlan_inst_custom_status, 'content': 'Check [network bandwidth, Median; Mbps]',
                        'expected': str(base_on_l3ha_vxlan_inst_median),
                         'actual': str(on_l3ha_vxlan_inst_median)},
                        {'status_id': 1, 'content': 'Check [deviation; pcs]', 'expected': str(base_on_l3ha_vxlan_inst_stdev),
                         'actual': str(on_l3ha_vxlan_inst_stdev)}]

custom_res_on_l3ha_vlan_nodes = [{'status_id': on_l3ha_vlan_nodes_custom_status, 'content': 'Check [network bandwidth, Median; Mbps]',
                        'expected': str(base_on_l3ha_vlan_nodes_median),
                         'actual': str(on_l3ha_vlan_nodes_median)},
                        {'status_id': 1, 'content': 'Check [deviation; pcs]', 'expected': str(base_on_l3ha_vlan_nodes_stdev),
                         'actual': str(on_l3ha_vlan_nodes_stdev)}]

custom_res_on_l3ha_vlan_inst = [{'status_id': on_l3ha_vlan_inst_custom_status, 'content': 'Check [network bandwidth, Median; Mbps]',
                        'expected': str(base_on_l3ha_vlan_inst_median),
                         'actual': str(on_l3ha_vlan_inst_median)},
                        {'status_id': 1, 'content': 'Check [deviation; pcs]', 'expected': str(base_on_l3ha_vlan_inst_stdev),
                         'actual': str(on_l3ha_vlan_inst_stdev)}]

### Global results for tests
off_dvr_vxlan_inst = {'test_id': test_off_dvr_vxlan_inst, 'status_id': off_dvr_vxlan_inst_glob_status, 'version': str(version),
                 'custom_test_case_steps_results': custom_res_off_dvr_vxlan_inst}
off_dvr_vlan_inst = {'test_id': test_off_dvr_vlan_inst, 'status_id': off_dvr_vlan_inst_glob_status, 'version': str(version),
                  'custom_test_case_steps_results': custom_res_off_dvr_vlan_inst}
on_dvr_vxlan_inst = {'test_id': test_on_dvr_vxlan_inst, 'status_id': on_dvr_vxlan_inst_glob_status, 'version': str(version),
                  'custom_test_case_steps_results': custom_res_on_dvr_vxlan_inst}
on_dvr_vlan_inst = {'test_id': test_on_dvr_vlan_inst, 'status_id': on_dvr_vlan_inst_glob_status, 'version': str(version),
                   'custom_test_case_steps_results': custom_res_on_dvr_vlan_inst}

on_l3ha_vxlan_nodes = {'test_id': test_on_l3ha_vxlan_nodes, 'status_id': on_l3ha_vxlan_nodes_glob_status, 'version': str(version),
                   'custom_test_case_steps_results': custom_res_on_l3ha_vxlan_nodes}
on_l3ha_vxlan_inst = {'test_id': test_on_l3ha_vxlan_inst, 'status_id': on_l3ha_vxlan_inst_glob_status, 'version': str(version),
                   'custom_test_case_steps_results': custom_res_on_l3ha_vxlan_inst}
on_l3ha_vlan_nodes = {'test_id': test_on_l3ha_vlan_nodes, 'status_id': on_l3ha_vlan_nodes_glob_status, 'version': str(version),
                   'custom_test_case_steps_results': custom_res_on_l3ha_vlan_nodes}
on_l3ha_vlan_inst = {'test_id': test_on_l3ha_vlan_inst, 'status_id': on_l3ha_vlan_inst_glob_status, 'version': str(version),
                   'custom_test_case_steps_results': custom_res_on_l3ha_vlan_inst}

### List of global results
results_list = [off_dvr_vxlan_inst, off_dvr_vlan_inst, on_dvr_vxlan_inst, on_dvr_vlan_inst, on_l3ha_vxlan_nodes, on_l3ha_vxlan_inst, on_l3ha_vlan_nodes, on_l3ha_vlan_inst]

### forming dict for testrail with all results
results_all_dict = {'results': results_list}

print results_all_dict

client.send_post('add_results/{}'.format(run_id), results_all_dict)

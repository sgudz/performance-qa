import ConfigParser
import base64
import json
import urllib2
import re
try: 
    from BeautifulSoup import BeautifulSoup
except ImportError:
    from bs4 import BeautifulSoup

def parse_results():
	data = open('/root/ceph_report.html')
	structure = str(data.readlines())
	soup = BeautifulSoup(structure, 'html.parser')
	tables1 = str(soup.find_all(class_="table table-bordered table-striped")[1])
	tables2 = str(soup.find_all(class_="table table-bordered table-striped")[2])
	tables3 = str(soup.find_all(class_="table table-bordered table-striped")[3])
	soup1 = BeautifulSoup(tables1, 'html.parser')
	soup2 = BeautifulSoup(tables2, 'html.parser')
	soup3 = BeautifulSoup(tables3, 'html.parser')
	rrd4k_data = soup1.find_all('td')[3].string
	rwd4k_data = soup1.find_all('td')[5].string
	rrd16MiB_data = soup2.find_all('td')[3].string
	rwd16MiB_data = soup2.find_all('td')[5].string
	try:
		rws10ms_data = int(soup3.find_all('td')[3].string)
	except ValueError:
		rws10ms_data = 0
	try:
		rws30ms_data = int(soup3.find_all('td')[5].string)
	except ValueError:
        	rws30ms_data = 0
        if "=" in str(soup3.find_all('td')[7].string):
        	rws100ms_data = int(soup3.find_all('td')[7].string[2:])
        else:
        	rws100ms_data = int(soup3.find_all('td')[7].string)

	rws100ms_data = int(soup3.find_all('td')[7].string[2:])
	rrd4k_iops = int(re.findall(r"[\d']+", rrd4k_data)[0])
	rwd4k_iops = int(re.findall(r"[\d']+", rwd4k_data)[0])
	rrd16MiB_bandwidth = int(re.findall(r"[\d']+", rrd16MiB_data)[0])
	rwd16MiB_bandwidth = int(re.findall(r"[\d']+", rwd16MiB_data)[0])
	rrd4k_dev = int(re.findall(r"[\d']+", rrd4k_data)[-1])
	rwd4k_dev = int(re.findall(r"[\d']+", rwd4k_data)[-1])
	rrd16MiB_dev = int(re.findall(r"[\d']+", rrd16MiB_data)[-1])
	rwd16MiB_dev = int(re.findall(r"[\d']+", rwd16MiB_data)[-1])
	print rws100ms_data
	return dict({"rws10ms_data": rws10ms_data, "rws30ms_data": rws30ms_data, "rws100ms_data": rws100ms_data, "rrd4k_iops": rrd4k_iops, "rwd4k_iops": rwd4k_iops, "rrd16MiB_bandwidth": rrd16MiB_bandwidth, "rwd16MiB_bandwidth": rwd16MiB_bandwidth, "rrd4k_dev": rrd4k_dev, "rwd4k_dev": rwd4k_dev, "rrd16MiB_dev": rrd16MiB_dev, "rwd16MiB_dev": rwd16MiB_dev})

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
fuel_ip = dict(parser.items('fuel'))['fuel_ip']
repl = int(dict(parser.items('testrail'))['repl'])
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
        if "Repl: {}".format(repl) in item['title'] and not "[deprecated]" in item['title']:
            test_names[item['title']] = item['id']
    return test_names


### Define test id's for each case
test_4kib_read = test_4kib_write = test_16mib_read = test_16mib_write = test_latency_10_ms = test_latency_30_ms = test_latency_100_ms = None
list_t = get_tests_ids()
for item in list_t.keys():
    if "4 KiB blocks; Read" in item:
        test_4kib_read = list_t[item]
    elif "4 KiB blocks; Write" in item:
        test_4kib_write = list_t[item]
    elif "16MiB blocks; Read" in item:
        test_16mib_read = list_t[item]
    elif "16MiB blocks; Write" in item:
        test_16mib_write = list_t[item]
    elif "latency 10ms" in item:
        test_latency_10_ms = list_t[item]
    elif "latency 30ms" in item:
        test_latency_30_ms = list_t[item]
    elif "latency 100ms" in item:
        test_latency_100_ms = list_t[item]

### Baseline data
base_read_16mib_median = client.send_get('get_test/{}'.format(test_16mib_read))['custom_test_case_steps'][0]['expected']
base_read_16mib_stdev = client.send_get('get_test/{}'.format(test_16mib_read))['custom_test_case_steps'][1]['expected']
base_write_16mib_median = client.send_get('get_test/{}'.format(test_16mib_write))['custom_test_case_steps'][0]['expected']
base_write_16mib_stdev = client.send_get('get_test/{}'.format(test_16mib_write))['custom_test_case_steps'][1]['expected']
base_read_4kib_median = client.send_get('get_test/{}'.format(test_4kib_read))['custom_test_case_steps'][0]['expected']
base_read_4kib_stdev = client.send_get('get_test/{}'.format(test_4kib_read))['custom_test_case_steps'][1]['expected']
base_write_4kib_median = client.send_get('get_test/{}'.format(test_4kib_write))['custom_test_case_steps'][0]['expected']
base_write_4kib_stdev = client.send_get('get_test/{}'.format(test_4kib_write))['custom_test_case_steps'][1]['expected']
base_latency_10_ms = client.send_get('get_test/{}'.format(test_latency_10_ms))['custom_test_case_steps'][0]['expected']
base_latency_30_ms = client.send_get('get_test/{}'.format(test_latency_30_ms))['custom_test_case_steps'][0]['expected']
base_latency_100_ms = client.send_get('get_test/{}'.format(test_latency_100_ms))['custom_test_case_steps'][0]['expected']

### Actual data
read_16mib_median = parse_results()["rrd16MiB_bandwidth"]
read_16mib_stdev = parse_results()["rrd16MiB_dev"]
write_16mib_median = parse_results()["rwd16MiB_bandwidth"]
write_16mib_stdev = parse_results()["rwd16MiB_dev"]
read_4kib_median = parse_results()["rrd4k_iops"]
read_4kib_stdev = parse_results()["rrd4k_dev"]
write_4kib_median = parse_results()["rwd4k_iops"]
write_4kib_stdev = parse_results()["rwd4k_dev"]
latency_10_ms = parse_results()["rws10ms_data"]
latency_30_ms = parse_results()["rws30ms_data"]
latency_100_ms = parse_results()["rws100ms_data"]

### Default status
read_16mib_glob_status = read_16mib_custom_status = 1
read_4kib_glob_status = read_4kib_custom_status = 1
write_16mib_glob_status = write_16mib_custom_status = 1
write_4kib_glob_status = write_4kib_custom_status = 1
latency_10_ms_glob_status = latency_10_ms_custom_status = 1
latency_30_ms_glob_status = latency_30_ms_custom_status = 1
latency_100_ms_glob_status = latency_100_ms_custom_status = 1

### Define status for tests, based on Baseline - 20%
if read_16mib_median < float(base_read_16mib_median) * 0.8:
    read_16mib_glob_status = read_16mib_custom_status = 5
if read_4kib_median < float(base_read_4kib_median) * 0.8:
    read_4kib_glob_status = read_4kib_custom_status = 5
if write_16mib_median < float(base_write_16mib_median) * 0.8:
    write_16mib_glob_status = write_16mib_custom_status = 5
if write_4kib_median < float(base_write_4kib_median) * 0.8:
    write_4kib_glob_status = write_4kib_custom_status = 5
if latency_10_ms < float(base_latency_10_ms) * 0.8:
    latency_10_ms_glob_status = latency_10_ms_custom_status = 5
if latency_30_ms < float(base_latency_30_ms) * 0.8:
    latency_30_ms_glob_status = latency_30_ms_custom_status = 5
if latency_100_ms < float(base_latency_100_ms) * 0.8:
    latency_100_ms_glob_status = latency_100_ms_custom_status = 5

### Custom results for tests
custom_res_4kib_read = [{'status_id': read_4kib_custom_status, 'content': 'Check [Operations per second Median; iops]',
                         'expected': str(base_read_4kib_median), 'actual': str(read_4kib_median)},
                        {'status_id': 1, 'content': 'Check [deviation; %]', 'expected': str(base_read_4kib_stdev),
                         'actual': str(read_4kib_stdev)}]
custom_res_4kib_write = [{'status_id': write_4kib_custom_status, 'content': 'Check [Operations per second Median; iops]',
                        'expected': str(base_write_4kib_median),
                         'actual': str(write_4kib_median)},
                        {'status_id': 1, 'content': 'Check [deviation; %]', 'expected': str(base_write_4kib_stdev),
                         'actual': str(write_4kib_stdev)}]
custom_res_16mib_read = [{'status_id': read_16mib_custom_status, 'content': 'Check [bandwidth Median; MiBps]',
                         'expected': str(base_read_16mib_median),
                         'actual': str(read_16mib_median)},
                        {'status_id': 1, 'content': 'Check [deviation; %]', 'expected': str(base_read_16mib_stdev),
                         'actual': str(read_16mib_stdev)}]
custom_res_16mib_write = [{'status_id': write_16mib_custom_status, 'content': 'Check [bandwidth Median; MiBps]',
                         'expected': str(base_write_16mib_median),
                         'actual': str(write_16mib_median)},
                        {'status_id': 1, 'content': 'Check [deviation; %]', 'expected': str(base_write_16mib_stdev),
                         'actual': str(write_16mib_stdev)}]
custom_res_latency_10 = [{'status_id': latency_10_ms_custom_status, 'content': 'Check [operation per sec, iops]',
                        'expected': str(base_latency_10_ms), 'actual': str(latency_10_ms)}]
custom_res_latency_30 = [{'status_id': latency_30_ms_custom_status, 'content': 'Check [operation per sec, iops]',
                        'expected': str(base_latency_30_ms), 'actual': str(latency_30_ms)}]
custom_res_latency_100 = [{'status_id': latency_100_ms_custom_status, 'content': 'Check [operation per sec, iops]',
                        'expected': str(base_latency_100_ms), 'actual': str(latency_100_ms)}]

### Global results for tests
res_4kib_read = {'test_id': test_4kib_read, 'status_id': read_4kib_glob_status, 'version': str(version),
                 'custom_test_case_steps_results': custom_res_4kib_read}
res_4kib_write = {'test_id': test_4kib_write, 'status_id': write_4kib_glob_status, 'version': str(version),
                  'custom_test_case_steps_results': custom_res_4kib_write}
res_16mib_read = {'test_id': test_16mib_read, 'status_id': read_16mib_glob_status, 'version': str(version),
                  'custom_test_case_steps_results': custom_res_16mib_read}
res_16mib_write = {'test_id': test_16mib_write, 'status_id': write_16mib_glob_status, 'version': str(version),
                   'custom_test_case_steps_results': custom_res_16mib_write}
res_latency_10 = {'test_id': test_latency_10_ms, 'status_id': latency_10_ms_glob_status, 'version': str(version),
                  'custom_test_case_steps_results': custom_res_latency_10}
res_latency_30 = {'test_id': test_latency_30_ms, 'status_id': latency_30_ms_glob_status, 'version': str(version),
                  'custom_test_case_steps_results': custom_res_latency_30}
res_latency_100 = {'test_id': test_latency_100_ms, 'status_id': latency_100_ms_glob_status, 'version': str(version),
                   'custom_test_case_steps_results': custom_res_latency_100}
### List of global results
results_list = [res_4kib_read, res_4kib_write, res_16mib_read, res_16mib_write, res_latency_10, res_latency_30,
                res_latency_100]

### forming dict for testrail with all results
results_all_dict = {'results': results_list}

print results_all_dict

### Pushing all resalts to testrail
#client.send_post('add_results/{}'.format(run_id), results_all_dict)

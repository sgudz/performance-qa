#!/usr/bin/env python

import psycopg2 as db
import sys
from jinja2 import FileSystemLoader
from jinja2 import Environment

class Host(object):
  def __init__(self, name, ipmi_host, ipmi_pass, macs):
     self.name = name
     self.ipmi_host =  ipmi_host
     self.ipmi_pass = ipmi_pass
     self.macs = macs


INTERFACE_QUERY = """SELECT 
  server_interfaces.name, 
  server_interfaces.mac
FROM 
  public.server_interfaces 
WHERE 
  server_interfaces.server_id = '{}' 
ORDER BY server_interfaces.name;"""


HOST_QUERY = """SELECT
  servers._id,
  servers.name,
  servers.node_ip,
  servers.node_password
FROM
  public.environments,
  public.servers
WHERE
  servers.allocated_env_id = environments._id
  AND environments.name = '{}'
ORDER BY servers.name;"""

hosts = []  

#db.connect('postgresql://rally:Ra11y@172.18.160.54/scaletool')
conn = db.connect("dbname='scaletool' user='rally' host='172.18.160.54' password='Ra11y'")
cur = conn.cursor()
cur.execute(HOST_QUERY.format(sys.argv[1]))
for host in cur.fetchall():
   ifaces = conn.cursor() 
   host_id, host_name, ipmi_ip, ipmi_pass = host
   ifaces.execute(INTERFACE_QUERY.format(host_id))
   macs = { name:mac for name, mac in ifaces.fetchall() }
   h = Host(host_name, ipmi_ip, ipmi_pass, macs)
   hosts.append(h) 
env = Environment()
env.loader = FileSystemLoader('.')
env_id = int(sys.argv[1])
template = env.get_template('env-{}.yaml.j2'.format(env_id))

print template.render(nodes=hosts, env_id=env_id)


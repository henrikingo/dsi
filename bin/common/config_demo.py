'''
Demo/test of config.py preview release.

cd dsi/docs/config-specs
python ../../bin/common/test_config_dict.py
'''
import logging
import pprint

from log import setup_logging
setup_logging(True)
LOG = logging.getLogger(__name__)
 
from config import ConfigDict

def test(cmd):
    print "#######################################################################"
    print cmd + ":"
    print
    print eval(cmd)


conf = ConfigDict('mongodb_setup')
conf.load()

#pprint.pprint(conf)
#pprint.pprint(conf.raw)
#pprint.pprint(conf.overrides)


print "TODO: this doesn't actually work. Seems like a limitation of python when sub-classing native type like dict: http://stackoverflow.com/questions/18317905/overloaded-iter-is-bypassed-when-deriving-from-dict"
print "Check that returning a dict() works correctly"
test( "dict(conf)" )
test( "dict(conf['workload_preparation']['on_workload_client'])" )

print
print "Basic checks"
test( "conf['workload_preparation']['on_workload_client']['download_files'][0]" )
test( "conf['workload_preparation']['on_workload_client']['download_files']" )
test( "conf['infrastructure_provisioning']['out']['workload_client'][0]" )
test( "conf['infrastructure_provisioning']['out']['workload_client'][0]['public_ip']" )

print
print "Value from overrides.yml"
test( "conf['infrastructure_provisioning']['tfvars']['configsvr_instance_type']" )
print
test( "conf['infrastructure_provisioning']['tfvars']" )

print
print "Value from defaults.yml"
test( "conf['mongodb_setup']['mongod_config_file']['port']" )
test( "conf['mongodb_setup']['mongod_config_file']['fork']" )



print
print "copy into other variable"
out = conf['infrastructure_provisioning']['out']

conf.raw['infrastructure_provisioning']['out']['workload_client'][0]['private_ip'] = "foo"
out.raw['workload_client'][0]['public_ip'] = "bar"
test( "type(out)")

test( "conf.raw['infrastructure_provisioning']['out']['workload_client']" )
test( "conf.root['infrastructure_provisioning']['out']['workload_client']" )
test( "out.raw['workload_client']" )
test( "out.root['infrastructure_provisioning']['out']['workload_client']" )
test( "out.overrides" )

print
print "print key from out"
test( "out['workload_client'][0]['public_ip']")

print
print
print "test ${variable.references}"

test( "conf['mongodb_setup']['topology'][0]['mongos'][0]['private_ip']" )
test( "conf['mongodb_setup']['meta']['hosts']" )

print
print "When getting mongod_config for a single node, it should contain both the common mongod_config, and node specific additions."
print "Note: This is the way to get the config in general: iterate over all mongod/mongos nodes, read their mongod_config and use it."
mycluster = conf['mongodb_setup']['topology'][0]
test( "str(mycluster['shard'][0]['mongod'][0]['mongod_config'])" )
test( "str(mycluster['shard'][2]['mongod'][0]['mongod_config'])" )
test( "mycluster['shard'][2]['mongod'][0]['mongod_config'].overrides" )
test( "mycluster['shard'][2]['mongod'][0]['mongod_config']['storage']['engine']" )
test( "mycluster['shard'][2]['mongod'][0]['mongod_config']['port']" )
test( "mycluster['shard'][2]['mongod'][0]['mongod_config']['fork']" )

mongod = mycluster['shard'][2]['mongod'][0]
test( "mongod.raw" )

print
print
print "set something"

conf['mongodb_setup']['out'] = { 'foo' : 'bar' }
print conf['mongodb_setup']['out']
print conf['mongodb_setup']['out']
print conf['mongodb_setup']['out']
print conf['mongodb_setup']['out']
print
conf['mongodb_setup']['out']['zoo'] = 'zar'
print conf['mongodb_setup']['out']
print

try:
    conf['foo'] = 'bar'
    print conf['foo']
except KeyError as e:
    print e

print "write the out file"
conf.dump()
print
print
print "Check that iterators (.keys() & .values()) work"
test( "conf.keys()" )
test( "conf['infrastructure_provisioning']['tfvars'].values()" )
test( "mycluster['shard'][2]['mongod'][0].values()" )



#TODO: API to get keys by their unique id


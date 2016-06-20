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

def demo(cmd):
    print "#######################################################################"
    print cmd
    print
    print str(eval(cmd))


def run_demo():
    global conf, out, mycluster, mongod

    conf = ConfigDict('mongodb_setup')
    conf.load()
    #demo( "str(conf)" )

    #pprint.pprint(conf)
    #pprint.pprint(conf.raw)
    #pprint.pprint(conf.overrides)


    print "TODO: this doesn't actually work. Seems like a limitation of python when sub-classing native type like dict: http://stackoverflow.com/questions/18317905/overloaded-iter-is-bypassed-when-deriving-from-dict"
    print "Check that returning a dict() works correctly"
    demo( "dict(conf)" )
    demo( "dict(conf['workload_preparation']['on_workload_client'])" )

    print
    print "Basic checks"
    demo( "conf['workload_preparation']['on_workload_client']['download_files'][0]" )
    demo( "conf['workload_preparation']['on_workload_client']['download_files']" )
    demo( "conf['infrastructure_provisioning']['out']['workload_client'][0]" )
    demo( "conf['infrastructure_provisioning']['out']['workload_client'][0]['public_ip']" )

    print
    print "Value from overrides.yml"
    demo( "conf['infrastructure_provisioning']['tfvars']['configsvr_instance_type']" )
    print
    demo( "conf['infrastructure_provisioning']['tfvars']" )

    print
    print "Value from defaults.yml"
    demo( "conf['mongodb_setup']['mongod_config_file']['net']['port']" )
    demo( "conf['mongodb_setup']['mongod_config_file']['processManagement']['fork']" )



    print
    print "copy into other variable"
    out = conf['infrastructure_provisioning']['out']

    conf.raw['infrastructure_provisioning']['out']['workload_client'][0]['private_ip'] = "foo"
    out.raw['workload_client'][0]['public_ip'] = "bar"
    demo( "type(out)")

    demo( "conf.raw['infrastructure_provisioning']['out']['workload_client']" )
    demo( "conf.root['infrastructure_provisioning']['out']['workload_client']" )
    demo( "out.raw['workload_client']" )
    demo( "out.root['infrastructure_provisioning']['out']['workload_client']" )
    demo( "out.overrides" )

    print
    print "print key from out"
    demo( "out['workload_client'][0]['public_ip']")

    print
    print
    print "test ${variable.references}"

    demo( "conf['mongodb_setup']['topology'][0]['mongos'][0]['private_ip']" )
    demo( "conf['mongodb_setup']['meta']['hosts']" )

    print
    print "When getting config_file for a single node, it should contain both the common mongod_config_file, and node specific config_file."
    print "Note: This is the way to get the config in general: iterate over all mongod/mongos nodes, read their config_file and use it."
    mycluster = conf['mongodb_setup']['topology'][0]
    demo( "str(mycluster['shard'][0]['mongod'][0]['config_file'])" )
    demo( "str(mycluster['shard'][2]['mongod'][0]['config_file'])" )
    demo( "mycluster['shard'][2]['mongod'][0]['config_file'].overrides" )
    demo( "mycluster['shard'][2]['mongod'][0]['config_file']['storage']['engine']" )
    demo( "mycluster['shard'][2]['mongod'][0]['config_file']['net']['port']" )
    demo( "mycluster['shard'][2]['mongod'][0]['config_file']['processManagement']['fork']" )

    mongod = mycluster['shard'][2]['mongod'][0]
    demo( "mongod.raw" )
    print
    print "this is the standalone node, has a slightly different path:"
    # Standalone node
    demo( "conf['mongodb_setup']['topology'][2]['config_file']" )
    
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
    conf.save()
    print
    print
    print "Check that iterators (.keys() & .values()) work"
    demo( "conf.keys()" )
    demo( "conf['infrastructure_provisioning']['tfvars'].values()" )
    demo( "mycluster['shard'][2]['mongod'][0].values()" )

    print
    print "Traversing the entire ConfigDict now, but not printing that..."
    str(conf)
    print "...done"

    #TODO: API to get keys by their unique id


if __name__ == '__main__':
    run_demo()
    

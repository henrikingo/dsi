'''
Demo/test of config.py preview release.

cd dsi/docs/config-specs
python ../../bin/common/test_config_dict.py
'''
from config import ConfigDict
import pprint

def demo(cmd):
    print "#######################################################################"
    print cmd + ":"
    print
    print eval(cmd)


def run_demo():
    conf = ConfigDict('mongodb_setup')
    conf.load()

    #pprint.pprint(conf)
    #pprint.pprint(conf.raw)
    #pprint.pprint(conf.overrides)


    demo( "conf['workload_preparation']['on_workload_client']['download_files'][0]" )
    demo( "conf['infrastructure_provisioning']['out']['workload_client'][0]" )
    demo( "conf['infrastructure_provisioning']['out']['workload_client'][0]['public_ip']" )
    
    print
    print "Value from overrides.yml"
    demo( "conf['infrastructure_provisioning']['tfvars']['configsvr_instance_type']" )
    print
    print "TODO: This doesn't work:"
    demo( "conf['infrastructure_provisioning']['tfvars']" )
    
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
    print "demo ${variable.references}"
    
    demo( "conf['mongodb_setup']['topology'][0]['mongos'][0]['private_ip']" )
    demo( "conf['mongodb_setup']['meta']['hosts']" )
    
    print
    print "When getting mongod_config for a single node, it should contain both the common mongod_config, and node specific additions."
    print "Note: This is the way to get the config in general: iterate over all mongod/mongos nodes, read their mongod_config and use it."
    mycluster = conf['mongodb_setup']['topology'][0]
    demo( "str(mycluster['shard'][0]['mongod'][0]['mongod_config'])" )
    demo( "str(mycluster['shard'][2]['mongod'][0]['mongod_config'])" )
    demo( "mycluster['shard'][2]['mongod'][0]['mongod_config'].overrides" )
    demo( "mycluster['shard'][2]['mongod'][0]['mongod_config']['storage']['engine']" )
    
    mongod = mycluster['shard'][2]['mongod'][0]
    demo( "mongod.raw" )
    
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
        demo( "conf.keys()" )
        demo( "conf['infrastructure_provisioning']['tfvars'].values()" )
        demo( "mycluster['shard'][2]['mongod'][0].values()" )
        

        #TODO: API to get keys by their unique id


if __name__ == '__main__':
    run_demo()

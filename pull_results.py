import requests
import json
import subprocess


base_url = 'https://evergreen.mongodb.com/api/2/task/performance_'
variant = 'linux_wt_standalone'
#variant = 'linux_mmap_standalone'
#variant = 'linux_wt_repl'
#variant = 'linux_mmap_repl'
Variant = variant.replace('_', '-')
githashplus = 'e61e8a9cbd3c5c1e5a46fc74f4b5ab5ce879c115_15_09_14_22_18_48'
githash = 'e61e8a9cbd3c5c1e5a46fc74f4b5ab5ce879c115'
variantgeo = variant + '_insert_'
#tasks = ['geo', 'insert', 'query', 'update', 'misc', 'singleThreaded', 'where']
tasks = ['insert', 'update', 'misc', 'singleThreaded']

for task in tasks : 
    for data in ['history', 'tags'] : 
        print 'Requesting %s' % base_url + variantgeo + githashplus + '/json/' + data + '/' + task + '/perf'
        r = requests.get(base_url + variantgeo + githashplus + '/json/' + data + '/' + task + '/perf')
        w = open(task + '.' + data + ".json", 'w')
        json.dump(r.json(), w)
        w.close()

for task in tasks :
    print 'python perf_regression_check.py -f %s --rev %s -t %s --refTag 3.0.6-Baseline --overrideFile ../etc/override.json --variant %s' % (task + '.history.json', githash, task + '.tags.json', variant)

    subprocess.call('python perf_regression_check.py -f %s --rev %s -t %s --refTag 3.0.6-Baseline --overrideFile ../etc/override.json --variant %s' % (task + '.history.json', githash, task + '.tags.json', Variant), shell=True)

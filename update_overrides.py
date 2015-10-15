#!/usr/bin/env python
import json
import requests
import perf_regression_check


tests = ["Where.SimpleNested.Where", "Where.ComplexNested", "Where.ReallyBigNestedComparison.Where"]
variants = ['linux_wt_standalone']
tag = '3.1.8-Baseline'


base_url = 'https://evergreen.mongodb.com/api/2/task/performance_'
# Replace this githash with a call to get most recent
githashplus = 'e5bd1ecd48d78900bafd64022200f94eb7be24c7_15_09_25_05_37_53'
githash = 'e5bd1ecd48d78900bafd64022200f94eb7be24c7'


replTasks = ['insert', 'update', 'misc', 'singleThreaded']
standTasks = ['insert', 'update', 'misc', 'singleThreaded', 'query', 'where', 'geo']
if 'linux_wt_repl' in variants or 'linux_mmap_repl' in variants : 
    tasks = replTasks
else : 
    tasks = standTasks

# Read in the original override.json file
overrides = json.load(open('../etc/override.json'))

# For each variant
for variant in variants:
    variantData = []
# Pull down the history data for that variant for all task types
    for task in tasks:
        Variant = variant.replace('_', '-')
        variantTask = variant + "_" + task + "_"
        print "Task is %s" % task
        print "Getting URL: %s" % base_url + variantTask + githashplus + '/json/tags/' + task + '/perf'
        r = requests.get(base_url + variantTask + githashplus + '/json/tags/' + task
 + '/perf')
        variantData.extend(r.json())
        
    # For each test name
    # Lookup entry for that in the histories, and replace in overrides
    tagHistory = perf_regression_check.History(variantData)
    for test in tests : 
        print "overriding overrides[%s]['reference'][%s]" % (Variant, test)
        overrides[Variant]["reference"][test] = tagHistory.seriesAtTag(test, tag)

# Write out new overrides
json.dump(overrides, open('../etc/override.json', 'w'), indent=4, separators=(',',':'), sort_keys=True)


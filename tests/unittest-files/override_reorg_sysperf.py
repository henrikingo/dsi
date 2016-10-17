#!/usr/bin/env python2.7
"""Script for one time reorg of the override json files. Adds task into the structure.

    After the reorg, the organization is: variant -> task -> test_name"""

import argparse
import json
import os.path
import sys


def main(args):
    dirs = [ "." ]
    files = [ "system_perf_override.json"
             ,"delete.system_perf.all.BF-1418.json.ok"
            #,"delete.system_perf.reference.PERF-335.json.ok"
            #,"delete.system_perf.threshold.PERF-335.json.ok"
            ]

    override_types = ["reference", "ndays", "threshold"]


    for dir in dirs:
        for file in files:
            print dir, file
            orig_file = dir+"/"+file
            new_file  = dir+"/"+file
            if not os.path.isfile( orig_file ):
                continue

            with open(orig_file) as file_handle:
                overrides = json.load(file_handle)

            new_overrides = {}

            for variantkey, variant in overrides.iteritems():
                for override_type_key, override_type in variant.iteritems():
                    for testkey, test in override_type.iteritems():
                        print variantkey, override_type_key, testkey
                        
                        taskpart = testkey.split("_")[0]
                        taskpart2 = testkey.split("_")[1]
                        print taskpart
                        
                        task_postfix = ""
                        if taskpart == "ycsb":
                            task = "industry_benchmarks"
                        elif taskpart=="initialsync" or taskpart2=="initialsync":
                            task = "initialsync"
                        else:
                            task = "core_workloads"

                        if taskpart == "cloneOneDB":
                            task_postfix = "_dr"

                        engine = testkey.split("-")[-1]
                        if engine == "wiredTiger":
                            engine = "WT"
                        elif engine == "mmapv1":
                            engine = "MMAPv1"
                        else:
                            raise Exception("Cannot happen")
                        
                        task = task + "_" + engine + task_postfix

                        set_new_override(new_overrides, variantkey, task, override_type_key, testkey, test)
                        # The validation test requires all override types to exist, at least with empty object value
                        for type in override_types:
                            if not type in new_overrides[variantkey][task].keys():
                                new_overrides[variantkey][task][type] = {}

            with open(new_file, 'w') as file_handle:
                json.dump(new_overrides, file_handle, indent=4, separators=[',', ':'], sort_keys=True)


def set_new_override(new_overrides, variantkey, task, override_type_key, testkey, test):
    if variantkey not in new_overrides:
        new_overrides[variantkey] = {}
    if task not in new_overrides[variantkey]:
        new_overrides[variantkey][task] = {}
    if override_type_key not in new_overrides[variantkey][task]:
        new_overrides[variantkey][task][override_type_key] = {}
    if testkey not in new_overrides[variantkey][task][override_type_key]:
        new_overrides[variantkey][task][override_type_key][testkey] = {}

    new_overrides[variantkey][task][override_type_key][testkey] = test
    print variantkey + "->" + task + "->" + override_type_key + "->" + testkey


if __name__ == '__main__':
    main(sys.argv[1:])

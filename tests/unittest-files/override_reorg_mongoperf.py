#!/usr/bin/env python2.7
"""Script for one time reorg of the override json files. Adds task into the structure.

    After the reorg, the organization is: variant -> task -> test_name"""

import argparse
import json
import os.path
import sys


def main(args):
    dirs = [ "." ]
    #files = [ "delete.perf.all.noise.json.ok", "delete.perf.threshold.PERF-443.json.ok", "delete.perf.reference.PERF-443.json.ok"]
    #files = ["perf_override.json", "perf_delete.json", "perf_delete_unique_test.json"]
    #files = [ "update_overrides.json.ok"]
    #files = [ "delete_update_latest.json.ok" ]
    #files = [ "update_override_exp.json.ok" ]
    #files = [ "delete_update_override.json.ok" ]
    #files = [ "delete.perf.all.PERF-755.json.ok" ]
    #files = [ "update_override_threshold_exp.json.ok" ]
    files = [ "update_ref_no_ticket.json.ok" ]
    override_types = ["reference", "ndays", "threshold"]


    for dir in dirs:
        for file in files:
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
                        taskpart = testkey.split(".")[0]

                        print taskpart

                        if taskpart == "Aggregation":
                            task = "aggregation"
                        elif taskpart=="Commands":
                            task = "misc"
                        elif taskpart=="Geo":
                            task = "geo"
                        elif taskpart=="Insert":
                            task = "insert"
                        elif taskpart=="Inserts":
                            task = "insert"
                        elif taskpart=="Mixed":
                            task = "misc"
                        elif taskpart=="MultiUpdate":
                            task = "update"
                        elif taskpart=="Queries":
                            task = "query"
                        elif taskpart=="Remove":
                            task = "misc"
                        elif taskpart=="Update":
                            task = "update"
                        elif taskpart=="Where":
                            task = "where"
                        elif taskpart=="Insert":
                            task = "insert"
                        else:
                            raise Exception("Cannot happen")

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

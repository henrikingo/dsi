# Copyright 2016 MongoDB Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Module of utility functions for analysis"""

from __future__ import absolute_import
import json

from evergreen.history import History

def get_json(filename):
    """ Load a file and parse it as json """
    return json.load(open(filename, 'r'))

def read_histories(variant, hfile, tfile, ofile):
    ''' Set up result histories from various files and returns the
    tuple (history, tag_history, overrides):
     history - this series include the run to be checked, and previous or NDays
     tag_history - this is the series that holds the tag build as comparison target
     overrides - this series has the override data to avoid false alarm or fatigues
    '''

    tag_history = None
    history = History(get_json(hfile))
    if tfile:
        tag_history = History(get_json(tfile))
    # Default empty override structure
    overrides = {'ndays': {}, 'reference': {}, 'threshold': {}}
    if ofile:
        # Read the overrides file
        foverrides = get_json(ofile)
        # Is this variant in the overrides file?
        if variant in foverrides:
            overrides = foverrides[variant]
    return(history, tag_history, overrides)

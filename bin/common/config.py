#!/usr/bin/env python2.7

import logging
import os.path
import re
import yaml

import pprint

LOG = logging.getLogger(__name__)

class ConfigDict(dict):
    'Get/Set API for DSI (Distributed Performance 2.0) config files (dsi/docs/)'
    modules = ['infrastructure_provisioning',
               'system_setup',
               'workload_preparation',
               'mongodb_setup',
               'test_control',
               'analysis',
               '_internal'];

    '''The dictionary wrapped by this ConfigDict. When you access["sub"]["keys"], this contains the substructure as well.'''
    raw = {}

    '''The dictionary holding contents of the *.override.yml files.
    
    Leaf values from overrides are "upserted" onto the values in raw during __getitem__().'''
    overrides = {}
    
    '''The complete config dictionary. 
    
    Initially this is equal to self, but then stays at the same root forever.
    This is used to substitute ${variable.references}, which can point anywhere into the config,
    not just the sub-structure currently held in self.raw.'''
    root = None
    
    '''When descending to sub keys, this is the current path from root.
    
    Used in __setitem__() to set the value into the root dictionary.'''
    path = []

    def __init__(self, which_module_am_i):
        self.assert_valid_module(which_module_am_i)
        self.module = which_module_am_i
        self.root = self

    def load(self):
        '''Populate this dict with contents of module_name.yml, module_name.out.yml and module_name.override.yml files.'''
        for m in self.modules :
            fname = m + '.yml'
            if os.path.isfile(fname):
                f = open( fname )
                self.raw[m] = yaml.load(f)
                f.close()
            fname = m + '.out.yml'
            if os.path.isfile(fname):
                f = open( fname )
                # Note: The .out.yml files will add a single top level key: 'out'
                out = yaml.load(f)
                if type(out) is dict :
                    self.raw[m].update(out)
                f.close()
        fname = 'overrides.yml'
        if os.path.isfile(fname):
            f = open( fname )
            self.overrides = yaml.load(f)
            f.close()
        return self

    def dump(self):
        '''Write contents of self.raw[self.module]['out'] to module_name.out.yaml'''
        f = open( self.module + '.out.yml', 'w' )
        f.write( yaml.dump( self.raw[self.module]['out'], default_flow_style=False ) )
        f.close()

    def assert_valid_module(self, module):
        try:
            self.modules.index(module)
        except ValueError:
            raise ValueError('This is not a valid DSI module: ' + module)

    ### Magic methods that make this object behave like a dict

    def __repr__(self):
        to_return = '{'
        i = 0
        for key in self.keys():
            if i > 0:
                to_return += ", "
            if type(key) is basestring:
                to_return += "'" + key + "': "
            else:
                to_return += str(key) + ": "
            to_return += str(self[key])
            i += 1
        to_return += '}'
        return to_return

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        '''Return list of keys, taking into account overrides.'''
        return list( set(self.raw.keys()) | set(self.overrides.keys()) )
    
    def iterkeys(self):
        for key in self.keys():
            yield (key,self[key])
    
    def __iter__(self):
        return self.iterkeys()

    def values(self):
        '''Return list of keys, taking into account overrides.'''
        to_return = []
        for k, v in self:
            to_return.append(v)
        return to_return

    def __getitem__(self, key):
        '''Return dict item, after applying overrides and ${variable.references}'''
        to_return = self.descend_key_and_apply_overrides(key)
        to_return = self.variable_references(to_return)
        return to_return

    def __setitem__(self, key, value):
        self.assert_writeable_path(key)
        self.raw[key] = value
        # Set the same element in self.root (this is the one that sticks)
        to_set = self.root.raw
        for element in self.path:
            to_set = to_set[element]
        to_set[key] = value


    ### __getitem__() helpers            
    def descend_key_and_apply_overrides(self, key):
        '''Return the key, but (for leaf nodes only) if an override exists, return the override value.
        
           The twist is that override can exist but be None (such as an empty list element), in which
           case we still return the value from raw. (It's not possible to delete a value, 
           or set to None, with override.)'''
        #print "####################################################################################"
        #print "descend_... : " + self.module + " " + key
        
        v = None

        # Check magic mongod_config/mongos_config/configsvr_config keys first
        # Note to reader: on first time, skip this, then come back to this when you understand everything else first.
        v = self.magic_mongo_config(key)
        if v:
            return v

        if self.overrides and not isinstance( self.raw.get(key,"default string"), (list, dict) ) :
            v = self.overrides.get(key, None)
        # And if none of the above apply, we just get the value from the dict as normal:
        if  v == None :
            v = self.raw[key]

        to_return = self.wrap_as_config_dict(key, v)
        
        # While descending a dict, keep the same subtree of overrides.
        # For a leaf node, the override is already applied.
        # For a list, either of the above applies to the list elements.
        if type(to_return) is ConfigDict :
            # to_return.overrides exists if we're returning from magic_mongo_config(). If so, keep it.
            if type( self.overrides ) is dict and not to_return.overrides :
                to_return.overrides = self.overrides.get(key, {})

        return to_return

    def wrap_as_config_dict(self, key, v):
        '''If item to return is a dict, return a ConfigDict, otherwise return as is.
        
        This is to keep the ConfigDict behavior when descending into the dictionary
        like conf['mongodb_setup']['mongos_config']...
        '''
        if type(v) is dict :
            to_return = ConfigDict(self.module)
            to_return.raw = v
            to_return.root = self.root
            # copy list (by value) and append the newest key
            to_return.path = list(self.path)
            to_return.path.append(key)
        elif type(v) is list :
            to_return = []
            for listv in v:
                child = self.wrap_as_config_dict(key, listv)
                if type(child) is ConfigDict:
                    # Store list index as part of the path for the elements in this list
                    child.path.append( len(to_return) )
                to_return.append( child )
                
        else:
            to_return = v
        return to_return

    def variable_references(self, to_return):
        '''For leaf node that is a string, substitute ${variable.references}'''
        # str and unicode strings have the common parent class basestring.
        if isinstance( to_return, basestring ):
            values = []
            m = re.findall(r"\$\{(.*?)\}", to_return)
            if m :
                for match in m :
                    match = self.convert_config_path(match)
                    # Note that because self.root is itself a ConfigDict, if a referenced
                    # value would itself contain a ${variable.reference}, then it will
                    # automatically be substituted as part of the next line too.
                    values.append( eval("self.root"+match) )
                between_values = re.split(r"\$\{.*?\}", to_return)
                to_return = between_values.pop(0)
                while len(values) > 0 :
                    to_return += values.pop(0)
                    to_return += between_values.pop(0)
        return to_return

    def convert_config_path(self, ref):
        '''Convert string path.like.0.this into ["path"]["like"][0]["this"]'''
        parts = ref.split('.')
        for i in range(0, len(parts)) :
            if not self.is_number(parts[i]) :
                parts[i] = '"' + parts[i] + '"'
        return '[' + ']['.join(parts) + ']'

    def is_number(self, str):
        try:
            float(str)
            return True
        except ValueError:
            return False

    def magic_mongo_config(self, key):
        '''If key is a mongod_config, mongos_config or configsvr_config key for a node in a mongodb_setup.topology
        
           we need to magically return the common mongod/s_config merged with contents of this key.
           TODO: Do we require the common mongod_config_file to exist? 
           Some non-default options like fork are needed for anything to work. The below code will not raise exception if no config exists.'''

        v = None
        if     len(self.path) > 3 and \
               self.path[0]  == 'mongodb_setup' and \
               self.path[1]  == 'topology' and \
               self.is_number( self.path[2] ) and \
               (self.path[-1] in ('mongod', 'mongos', 'configsvr') or self.is_number(self.path[-1]) ) and \
               key in ('mongod_config', 'mongos_config', 'configsvr_config') :

            # Note: In the below 2 lines, overrides and ${variables} are already applied
            common_config = self.root['mongodb_setup'].get(key+'_file')
            node_specific_config = self.raw.get(key,None)
            # Technically this works the same as if common_config was the raw value
            # and node_specific_config is a dict with overrides. So let's reuse some code...
            helper = ConfigDict('_internal')
            helper.raw = { key : common_config }
            helper.overrides = { key : node_specific_config }
            v = helper[key]

        return v


    ### __setitem__() helpers
    def assert_writeable_path(self, key):
        '''ConfigDict is read-only, except for self[self.module]['out'] namespace.'''
        if len(self.path) >= 2 and \
           self.path[0] == self.module and \
           self.path[1] == 'out':
                return True

        elif len(self.path) == 1 and \
             self.path[0] == self.module and \
             key == 'out':
                return True

        else:
                raise KeyError('Only values under self["' + self.module + '"]["out"] are settable in this object')

    def get_path(self, key=None):
        path_str = ''
        for element in self.path :
            if type(element) is str :
                path_str += '["' + element + '"]'
            else:
                path_str += '[' + str(element) + ']'
        if key != None :
            if type(key) is str :
                path_str += '["' + key + '"]'
            else:
                path_str += '[' + str(key) + ']'
        print path_str
        return path_str


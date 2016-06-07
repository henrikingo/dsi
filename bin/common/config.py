#!/usr/bin/env python2.7
'''ConfigDict class reads yaml config files and presents a dict() get/set API to read configs.'''

# pylint: disable=too-many-boolean-expressions,no-self-use
import logging
import os.path
import re
import yaml

from log import setup_logging

LOG = logging.getLogger(__name__)

class ConfigDict(dict):
    '''Get/Set API for DSI (Distributed Performance 2.0) config files (dsi/docs/).

    A ConfigDict class will read a multitude of yaml configuration files, and present
    them as a single python dictionary from where keys can be read, and some keys can also
    be set and ultimately written to a module_name.out.yml file.

    The value returned for a given key, say config['module_name']['key']['subkey'] is
    actually the result of overlaying several yaml files into what only seems to be a
    standard dictionary. The returned value is found in the various files in the following
    priority:

    overrides.yml
    module_name.yml
    defaults.yml
    raise KeyError'''
    modules = ['infrastructure_provisioning',
               'system_setup',
               'workload_preparation',
               'mongodb_setup',
               'test_control',
               'analysis',
               '_internal']

    '''The dictionary wrapped by this ConfigDict. When you access["sub"]["keys"], this contains the
    substructure as well.'''
    raw = {}

    '''The dictionary holding defaults, set in dsi/docs/config-specs/defaults.yml.

    If neither raw nor overrides specified a value for a key, the default value is returned from
    here.'''
    defaults = {}

    '''The dictionary holding contents of the *.override.yml files.

    Leaf values from overrides are "upserted" onto the values in raw during __getitem__().'''
    overrides = {}

    '''The complete config dictionary.

    Initially this is equal to self, but then stays at the same root forever.
    This is used to substitute ${variable.references}, which can point anywhere into the config,
    not just the sub-structure currently held in self.raw.'''
    root = None

    '''When descending to sub keys, this is the current path from root.

    Used in __setitem__() to set the value into the root dictionary.
    Also checked to see if we're at the path of a mongod_config_file, mongos_config_file or
    configsvr_config_file.'''
    path = []

    def __init__(self, which_module_am_i):
        dict.__init__(self)
        self.assert_valid_module(which_module_am_i)
        self.module = which_module_am_i
        self.root = self

    def load(self):
        '''Populate with contents of module_name.yml, module_name.out.yml, overrides.yml.'''

        file_name = '../../docs/config-specs/defaults.yml'
        file_handle = open(file_name)
        self.defaults = yaml.load(file_handle)
        file_handle.close()
        LOG.info('ConfigDict: Loaded: %s', file_name)

        for module_name in self.modules:
            file_name = module_name + '.yml'
            if os.path.isfile(file_name):
                file_handle = open(file_name)
                self.raw[module_name] = yaml.load(file_handle)
                file_handle.close()
                LOG.info('ConfigDict: Loaded: %s', file_name)
            file_name = module_name + '.out.yml'
            if os.path.isfile(file_name):
                file_handle = open(file_name)
                # Note: The .out.yml files will add a single top level key: 'out'
                out = yaml.load(file_handle)
                if isinstance(out, dict):
                    self.raw[module_name].update(out)
                file_handle.close()
                LOG.info('ConfigDict: Loaded: %s', file_name)

        file_name = 'overrides.yml'
        if os.path.isfile(file_name):
            file_handle = open(file_name)
            self.overrides = yaml.load(file_handle)
            file_handle.close()
            LOG.info('ConfigDict: Loaded: %s', file_name)

        return self

    def dump(self):
        '''Write contents of self.raw[self.module]['out'] to module_name.out.yaml'''
        file_name = self.module + '.out.yml'
        file_handle = open(file_name, 'w')
        file_handle.write(yaml.dump(self.raw[self.module]['out'], default_flow_style=False))
        file_handle.close()
        LOG.info('ConfigDict: Wrote file: %s', file_name)

    def assert_valid_module(self, module_name):
        '''Check that module_name is one of Distributed Performance 2.0 modules, or _internal.'''
        try:
            self.modules.index(module_name)
        except ValueError:
            raise ValueError('This is not a valid DSI module: ' + module_name)

    ### Implementation of dict API

    def __repr__(self):
        to_return = '{'
        i = 0
        for key in self.keys():
            if i > 0:
                to_return += ", "
            if isinstance(key, basestring):
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
        return list(set(self.raw.keys()) | set(self.overrides.keys()) | set(self.defaults.keys()))

    def iterkeys(self):
        for key in self.keys():
            yield (key, self[key])

    # pylint: disable=fixme,line-too-long
    # TODO: __iter__ isn't actually called if you do dict(instance_of_ConfigDict), so casting
    # to dict doesn't work. See http://stackoverflow.com/questions/18317905/overloaded-iter-is-bypassed-when-deriving-from-dict
    def __iter__(self):
        for key in self.keys():
            yield (key, self[key])

    def values(self):
        '''Return list of values, taking into account overrides.'''
        print "values()"
        to_return = []
        for key in self.keys():
            to_return.append(self[key])
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
        '''Return the key, but (for leaf nodes) if an override exists, return the override value.

           The twist is that override can exist but be None (such as an empty list element), in
           which case we still return the value from raw. (It's not possible to delete a value,
           or set to None, with override.)

           If no value exist, see if a default value exists.
           '''

        value = None

        # Check magic mongod_config/mongos_config/configsvr_config keys first
        # Note to reader: on first time, skip this, then come back to this when you understand
        # everything else first.
        value = self.magic_mongo_config(key)
        if value:
            return value

        if self.overrides and not isinstance(self.raw.get(key, "default string"), (list, dict)):
            value = self.overrides.get(key, None)
        # And if none of the above apply, we just get the value from the raw dict, or from defaults:
        if  value is None:
            value = self.raw.get(key, None)
        if value is None:
            value = self.defaults[key]


        to_return = self.wrap_as_config_dict(key, value)

        # While descending a dict, keep the same subtree of overrides.
        # For a leaf node, the override is already applied.
        # For a list, either of the above applies to the list elements.
        if isinstance(to_return, ConfigDict):
            # to_return.overrides is already set if we're returning from magic_mongo_config().
            # If so, keep it.
            if not to_return.overrides and isinstance(self.overrides, dict):
                to_return.overrides = self.overrides.get(key, {})

        return to_return

    def wrap_as_config_dict(self, key, value):
        '''If item to return is a dict, return a ConfigDict, otherwise return as is.

        This is to keep the ConfigDict behavior when descending into the dictionary
        like conf['mongodb_setup']['mongos_config']...
        '''
        if isinstance(value, dict):
            return_dict = ConfigDict(self.module)
            return_dict.raw = value
            if isinstance(self.defaults, dict):
                return_dict.defaults = self.defaults.get(key, {})
            return_dict.root = self.root
            # copy list (by value) and append the newest key
            return_dict.path = list(self.path)
            return_dict.path.append(key)
            return return_dict
        elif isinstance(value, list):
            return_list = []
            for listvalue in value:
                child = self.wrap_as_config_dict(key, listvalue)
                if isinstance(child, ConfigDict):
                    # Store list index as part of the path for the elements in this list
                    child.path.append(len(return_list))
                return_list.append(child)
            return return_list
        else:
            return value

    def variable_references(self, to_return):
        '''For leaf node that is a string, substitute ${variable.references}'''
        # str and unicode strings have the common parent class basestring.
        if isinstance(to_return, basestring):
            values = []
            matches = re.findall(r"\$\{(.*?)\}", to_return)
            if matches:
                for match in matches:
                    match = self.convert_config_path(match)
                    # Note that because self.root is itself a ConfigDict, if a referenced
                    # value would itself contain a ${variable.reference}, then it will
                    # automatically be substituted as part of the next line too.
                    values.append(eval("self.root"+match))
                between_values = re.split(r"\$\{.*?\}", to_return)
                to_return = between_values.pop(0)
                while len(values) > 0:
                    to_return += values.pop(0)
                    to_return += between_values.pop(0)
        return to_return

    def convert_config_path(self, ref):
        '''Convert string path.like.0.this into ["path"]["like"][0]["this"]'''
        parts = ref.split('.')
        for i in range(0, len(parts)):
            if not self.is_integer(parts[i]):
                parts[i] = '"' + parts[i] + '"'
        return '[' + ']['.join(parts) + ']'

    def magic_mongo_config(self, key):
        '''If key is a (mongod|mongos|configsvr)_config, key for a node in a mongodb_setup.topology

           we need to magically return the common mongod/s_config merged with contents of this key.
           TODO: Do we require the common mongod_config_file to exist?
           Some non-default options like fork are needed for anything to work. The below code will
           not raise exception if no config exists.'''

        value = None
        if     len(self.path) > 3 and \
               self.path[0] == 'mongodb_setup' and \
               self.path[1] == 'topology' and \
               self.is_integer(self.path[2]) and \
               (self.path[-1] in ('mongod', 'mongos', 'configsvr') or \
                self.is_integer(self.path[-1])) and \
               key in ('mongod_config', 'mongos_config', 'configsvr_config'):

            # Note: In the below 2 lines, overrides and ${variables} are already applied
            common_config = self.root['mongodb_setup'].get(key+'_file')
            node_specific_config = self.raw.get(key, {})
            # Technically this works the same as if common_config was the raw value
            # and node_specific_config is a dict with overrides. So let's reuse some code...
            helper = ConfigDict('_internal')
            helper.raw = {key : common_config}
            helper.overrides = {key : node_specific_config}
            value = helper[key]

        return value


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
            raise KeyError('Only values under self["' + self.module +
                           '"]["out"] are settable in this object')

    def get_path(self, key=None):
        '''Get self.path in a format that works with python eval("self"+self.get_path()).

        If key is given, it is appended to the path as the last key.'''
        path_str = ''
        for element in self.path:
            if isinstance(element, str):
                path_str += '["' + element + '"]'
            else:
                path_str += '[' + str(element) + ']'
        if key != None:
            if isinstance(key, str):
                path_str += '["' + key + '"]'
            else:
                path_str += '[' + str(key) + ']'
        return path_str

    def is_integer(self, astring):
        '''Return True if astring is an integer, false otherwise.'''
        try:
            int(astring)
            return True
        except ValueError:
            return False

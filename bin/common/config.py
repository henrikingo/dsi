"""ConfigDict class reads yaml config files and presents a dict() get/set API to read configs."""

import copy
import logging
import os.path
import re
import sys
import yaml

LOG = logging.getLogger(__name__)

class ConfigDict(dict):
    """Get/Set API for DSI (Distributed Performance 2.0) config files (dsi/docs/).

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
    raise KeyError"""
    modules = ['infrastructure_provisioning',
               'system_setup',
               'workload_preparation',
               'mongodb_setup',
               'test_control',
               'analysis',
               '_internal']

    def __init__(self, which_module_am_i):
        self.raw = {}
        """The dictionary wrapped by this ConfigDict. When you access["sub"]["keys"], this contains
        the substructure as well."""

        self.defaults = {}
        """The dictionary holding defaults, set in dsi/docs/config-specs/defaults.yml.

        If neither raw nor overrides specified a value for a key, the default value is returned from
        here."""

        self.overrides = {}
        """The dictionary holding contents of the *.override.yml files.

        Leaf values from overrides are "upserted" onto the values in raw during __getitem__()."""

        self.root = None
        """The complete config dictionary.

        Initially this is equal to self, but then stays at the same root forever.
        This is used to substitute ${variable.references}, which can point anywhere into the config,
        not just the sub-structure currently held in self.raw."""

        self.path = []
        """When descending to sub keys, this is the current path from root.

        Used in __setitem__() to set the value into the root dictionary.
        Also checked to see if we're at the path of a mongod/mongos/configsvr config_file."""

        super(ConfigDict, self).__init__()
        self.assert_valid_module(which_module_am_i)
        self.module = which_module_am_i
        self.root = self

    def load(self):
        """Populate with contents of module_name.yml, module_name.out.yml, overrides.yml."""

        # defaults.yml
        file_name = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 '..', '..', 'docs', 'config-specs', 'defaults.yml')
        file_handle = open(file_name)
        self.defaults = yaml.safe_load(file_handle)
        file_handle.close()
        LOG.info('ConfigDict: Loaded: %s', file_name)

        # All module_name.yml and module_name.out.yml
        for module_name in self.modules:
            file_name = module_name + '.yml'
            if os.path.isfile(file_name):
                file_handle = open(file_name)
                self.raw[module_name] = yaml.safe_load(file_handle)
                file_handle.close()
                LOG.info('ConfigDict: Loaded: %s', file_name)
            file_name = module_name + '.out.yml'
            if os.path.isfile(file_name):
                file_handle = open(file_name)
                # Note: The .out.yml files will add a single top level key: 'out'
                out = yaml.safe_load(file_handle)
                if isinstance(out, dict):
                    self.raw[module_name].update(out)
                file_handle.close()
                LOG.info('ConfigDict: Loaded: %s', file_name)

        # overrides.yml
        file_name = 'overrides.yml'
        if os.path.isfile(file_name):
            file_handle = open(file_name)
            self.overrides = yaml.safe_load(file_handle)
            file_handle.close()
            LOG.info('ConfigDict: Loaded: %s', file_name)

        return self

    def save(self):
        """Write contents of self.raw[self.module]['out'] to module_name.out.yaml"""
        file_name = self.module + '.out.yml'
        file_handle = open(file_name, 'w')
        out = {'out' : self.raw[self.module]['out']}
        file_handle.write(yaml.dump(out, default_flow_style=False))
        file_handle.close()
        LOG.info('ConfigDict: Wrote file: %s', file_name)

    def assert_valid_module(self, module_name):
        """Check that module_name is one of Distributed Performance 2.0 modules, or _internal."""
        if module_name not in self.modules:
            raise ValueError('This is not a valid DSI module: ' + module_name)

    ### Implementation of dict API

    def __repr__(self):
        str_representation = '{'
        i = 0
        for key in self.keys():
            if i > 0:
                str_representation += ", "
            if isinstance(key, basestring):
                str_representation += "'" + key + "': "
            else:
                str_representation += str(key) + ": "
            if isinstance(self[key], basestring):
                str_representation += "'" + str(self[key]) + "'"
            else:
                str_representation += str(self[key])
            i += 1
        str_representation += '}'
        return str_representation

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        """Return list of keys, taking into account overrides."""
        raw_keys = set()
        overrides_keys = set()
        defaults_keys = set()
        if isinstance(self.raw, dict):
            raw_keys = set(self.raw.keys())
        if isinstance(self.overrides, dict):
            overrides_keys = set(self.overrides.keys())
        if isinstance(self.defaults, dict):
            defaults_keys = set(self.defaults.keys())
        return list(raw_keys | overrides_keys | defaults_keys)

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
        """Return list of values, taking into account overrides."""
        return [self[key] for key in self.keys()]

    def __getitem__(self, key):
        """Return dict item, after applying overrides and ${variable.references}"""
        value = self.descend_key_and_apply_overrides(key)
        value = self.variable_references(key, value)
        return value

    def __setitem__(self, key, value):
        self.assert_writeable_path(key)
        self.raw[key] = value
        # Set the same element in self.root (this is the one that sticks)
        to_set = self.root.raw
        for element in self.path:
            to_set = to_set[element]
        to_set[key] = value

    def as_dict(self):
        # pylint: disable=line-too-long
        """Cast this DictConfig into a normal dict.

        Note that this is a supplement solution until we fix the issues arising from subclassing
        from dict / not being able to cast normally with dict(config).
        http://stackoverflow.com/questions/18317905/overloaded-iter-is-bypassed-when-deriving-from-dict
        """
        return ConfigDict.make_dict(self)

    ### __getitem__() helpers
    def descend_key_and_apply_overrides(self, key):
        """Return the key, but (for leaf nodes) if an override exists, return the override value.

           The twist is that override can exist but be None (such as an empty list element), in
           which case we still return the value from raw. (It's not possible to delete a value,
           or set to None, with override.)

           If no value exist, see if a default value exists.
           """
        value = None

        # Check the magic per node mongod_config/mongos_config/configsvr_config keys first.
        # Note to reader: on first time, skip this, then come back to this when you understand
        # everything else first.
        value = self.get_node_mongo_config(key)
        if value:
            return value

        if self.overrides and \
           isinstance(self.overrides, dict) and \
           not isinstance(self.raw.get(key, "some string"), (list, dict)):
            value = self.overrides.get(key, None)

        # And if none of the above apply, we just get the value from the raw dict, or from defaults:
        if  value is None:
            value = self.raw.get(key, None)
        if value is None and isinstance(self.defaults, dict):
            value = self.defaults.get(key, None)
        # We raise our own error to highlight that key really is missing, not a bug or anything.
        if value is None:
            raise KeyError("ConfigDict: Key not found: {}".format(key))

        value = self.wrap_dict_as_config_dict(key, value)

        # While descending a dict, keep the same subtree of overrides.
        # For a leaf node, the override is already applied.
        # For a list, either of the above applies to the list elements.
        if isinstance(value, ConfigDict):
            # value.overrides is already set if we're returning from get_node_mongo_config().
            # If so, keep it.
            if not value.overrides and isinstance(self.overrides, dict):
                value.overrides = self.overrides.get(key, {})

        return value

    def wrap_dict_as_config_dict(self, key, value):
        """If item to return is a dict, return a ConfigDict, otherwise return as is.

        This is to keep the ConfigDict behavior when descending into the dictionary
        like conf['mongodb_setup']['mongos_config']...
        """
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
                child = self.wrap_dict_as_config_dict(key, listvalue)
                if isinstance(child, ConfigDict):
                    # Store list index as part of the path for the elements in this list
                    child.path.append(len(return_list))
                return_list.append(child)
            return return_list
        else:
            return value

    def variable_references(self, key, value):
        """For leaf node that is a string, substitute ${variable.references}"""
        # str and unicode strings have the common parent class basestring.
        if isinstance(value, basestring):
            values = []
            matches = re.findall(r"\$\{(.*?)\}", value)
            if matches:
                for path in matches:
                    path_list = self.variable_path_as_list(path)
                    # Note that because self.root is itself a ConfigDict, if a referenced
                    # value would itself contain a ${variable.reference}, then it will
                    # automatically be substituted too, as part of the descend_root[key].
                    descend_root = self.root
                    for path_element in path_list:
                        try:
                            descend_root = descend_root[path_element]
                        except:
                            path_from_root = copy.copy(self.path)
                            path_from_root.append(key)
                            raise ValueError("ConfigDict error at {}: Cannot resolve variable "
                                             "reference '{}', error at '{}': {} {}"
                                             .format(path_from_root, path, path_element,
                                                     sys.exc_info()[0], sys.exc_info()[1]))
                    values.append(descend_root)
                between_values = re.split(r"\$\{.*?\}", value)

                # If the variable reference is the entire value, then return the referenced value
                # as it is, including preserving type. Otherwise, concatenate back into a string.
                if len(between_values) == 2 and \
                   between_values[0] == '' and \
                   between_values[1] == '':
                    return values[0]
                else:
                    value = between_values.pop(0)
                    while len(values) > 0:
                        value += values.pop(0)
                        value += between_values.pop(0)
        return value

    def variable_path_as_list(self, path):
        """Split path.like.0.this into parts and return the list."""
        # pylint: disable=no-self-use

        parts = path.split('.')
        # If an element in the path converts to integer, do so
        for i, element in enumerate(parts):
            if is_integer(element):
                parts[i] = int(element)
        return parts

    def get_node_mongo_config(self, key):
        """If key is a (mongod|mongos|configsvr)_config, key for a node in a mongodb_setup.topology

           we need to magically return the common mongod/s_config merged with contents of this key.
           Some non-default options like fork are needed for anything to work. The below code will
           not raise exception if no config exists."""
        # pylint: disable=too-many-boolean-expressions

        value = None
        if     len(self.path) > 3 and \
               self.path[0] == 'mongodb_setup' and \
               self.path[1] == 'topology' and \
               is_integer(self.path[2]) and \
               (self.path[-1] in ('mongod', 'mongos', 'configsvr') or \
                is_integer(self.path[-1])) and \
               key == ('config_file'):

            # Note: In the below 2 lines, overrides and ${variables} are already applied
            common_config = self.root['mongodb_setup'].get(self.topology_node_type()+'_config_file')
            node_specific_config = self.raw.get(key, {})
            # Technically this works the same as if common_config was the raw value
            # and node_specific_config is a dict with overrides. So let's reuse some code...
            helper = ConfigDict('_internal')
            helper.raw = {key : common_config}
            helper.overrides = {key : node_specific_config}
            value = helper[key]

        return value

    def topology_node_type(self):
        """Return one of mongod, mongos or configsvr by looking upwards in self.path

        Note: This only works when called from get_node_mongo_config(). We don't guard against
        random results if calling it from elsewhere."""
        if self.path[-1] in ('mongod', 'mongos', 'configsvr'):
            return self.path[-1]
        elif is_integer(self.path[-1]):
            return 'mongod'
        else:
            return None


    ### __setitem__() helpers
    def assert_writeable_path(self, key):
        """ConfigDict is read-only, except for self[self.module]['out'] namespace."""
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

    @staticmethod
    def make_dict(config):
        """Return a normal dictionary copy of the config"""
        if isinstance(config, dict):
            new_dict = {}
            for key, value in config:
                new_dict[key] = ConfigDict.make_dict(value)
        elif isinstance(config, list):
            new_dict = [ConfigDict.make_dict(item) for item in config]
        else:
            new_dict = config
        return new_dict
        
def is_integer(astring):
    """Return True if astring is an integer, false otherwise."""
    # pylint: disable=no-self-use
    try:
        int(astring)
        return True
    except ValueError:
        return False


#!/usr/bin/env python2.7
"""
MongoDB Setup but for Atlas clusters

Instead of creating our own MongoDB clusters, we make REST calls to Atlas instead.
"""
import argparse
import copy
import logging
import random
import sys

import common.atlas_client as atlas_client
import common.config
import common.log as log

LOG = logging.getLogger(__name__)


class AtlasSetup(object):
    """
    MongodbSetup for Atlas.
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(self, config):
        """
        Initialize the object from config.

        :param ConfigDict config: The DSI config.
        """
        self.config = config
        self.mongodb_setup = self.config['mongodb_setup']
        # Initialize empty objects here to simplify all later code
        if not "out" in self.mongodb_setup:
            self.mongodb_setup["out"] = {}
        if not "atlas" in self.mongodb_setup["out"]:
            self.mongodb_setup["out"]["atlas"] = {}
        if not "clusters" in self.mongodb_setup["out"]["atlas"]:
            self.mongodb_setup["out"]["atlas"]["clusters"] = []

        self.api = self.mongodb_setup["atlas"]["api"].as_dict()
        LOG.debug("Atlas api config = %s", self.api)
        self.api_credentials = {}
        self.api_credentials["user"] = self.config["runtime_secret"]["atlas_api_user"]
        self.api_credentials["key"] = self.config["runtime_secret"]["atlas_api_key"]
        LOG.debug("Atlas credentials = %s:%s***", self.api_credentials["user"],
                  self.api_credentials["key"][0:5])
        self.atlas_client = atlas_client.AtlasClient(self.api, self.api_credentials)

    def start(self):
        """
        Deploy cluster(s) as given in mongodb_setup.yml configuration.

        :return: True if all clusters succeeded.
        """
        # The intended use is to deploy as many clusters as specified in
        # mongodb_setup.atlas.clusters and then later shut them down via destroy().
        # Repeated calls to start() would generate new cluster(s) with new unique name(s).
        # I decided that would probably be a bad thing, so not supporting repeated start() without
        # calling destroy() in between.
        if self.mongodb_setup["out"]["atlas"]["clusters"]:
            LOG.error("Clusters already exist in mongodb_setup.out.atlas.clusters.")
            LOG.error("Please shutdown existing clusters first with atlas_teardown.py.")
            LOG.debug(self.mongodb_setup["out"])
            return False

        return all(
            self.create_cluster(atlas_cluster)
            for atlas_cluster in self.mongodb_setup["atlas"]["clusters"])

    def destroy(self):
        """
        Destroy the cluster(s) listed in `mongodb_setup.out.atlas.clusters`.
        """
        LOG.info("About to shutdown these Atlas clusters:  %s",
                 [obj["name"] for obj in self.mongodb_setup["out"]["atlas"]["clusters"]])
        return all(
            self.delete_cluster(atlas_cluster)
            for atlas_cluster in self.mongodb_setup["out"]["atlas"]["clusters"])

    def create_cluster(self, atlas_cluster):
        """
        Deploy single cluster.

        Waits until a cluster is ready (stateName). Generates and stores a unique cluster name to
        `mongodb_setup.out.atlas.clusters.*.name`.

        :param ConfigDict atlas_cluster: One cluster from mongodb_setup.atlas.clusters.*
        :return: True if successful.
        :raises HTTPError: As raised by requests.Response.raise_for_status().
        """
        name = self._generate_unique_name(atlas_cluster)
        body = atlas_cluster.as_dict()
        body["name"] = name

        LOG.info("Create %s Atlas %s with name: %s", body["providerSettings"]["instanceSizeName"],
                 body["clusterType"], body["name"])
        response = self.atlas_client.create_cluster(body)
        LOG.debug(response)
        # This response still lacks meta data, but we want to persist the cluster name asap
        self._save_create_response(response)
        response = self.atlas_client.await(name)
        LOG.debug(response)
        # Save MongoDB URI and such to mongodb_setup.out.yml
        self._save_create_response(response)
        LOG.info("Done creating %s Atlas %s with name: %s",
                 body["providerSettings"]["instanceSizeName"], body["clusterType"], body["name"])
        return True

    @staticmethod
    def _generate_unique_name(atlas_cluster):
        chars = "abcdefghijklmnopqrstuvwxyz"
        unique = ''.join([random.choice(chars) for _ in range(7)])
        return "dsi-{}-{}-{}".format(atlas_cluster["clusterType"],
                                     atlas_cluster["providerSettings"]["instanceSizeName"], unique)

    def _save_create_response(self, response):
        new_object = {}
        save_fields = ("name", "stateName", "mongoURI", "mongoURIWithOptions", "mongoURIUpdated")
        for key in save_fields:
            if key in response:
                new_object[key] = response[key]

        LOG.debug(new_object)
        # While this is a list, we actually lookup by cluster name.
        # An alternative design would have been for mongodb_setup.out.atlas.clusters to be a dict
        # keyed on name. That is really what this code is doing. But I wanted to keep it a list so
        # that it matches the list user provides in mongodb_setup.atlas.clusters.
        index = self._find_cluster_in_list(new_object)
        # assign and append() won't work in a ConfigDict, but works if I take out the list first
        clusters_list = self.mongodb_setup["out"]["atlas"]["clusters"]
        if index is not None:
            # Replace existing entry
            clusters_list[index] = new_object
        else:
            # New cluster / first save
            clusters_list.append(new_object)
        # Then assign the entire list back to the ConfigDict
        self.mongodb_setup["out"]["atlas"]["clusters"] = clusters_list

        LOG.debug(self.mongodb_setup["out"])
        self.config.save()  # Creates mongodb_setup.out.yml

    def delete_cluster(self, atlas_cluster):
        """
        Shutdown given cluster, using its name.

        :param ConfigDict atlas_cluster: An object from `mongodb_setup.out.atlas.clusters`. Must
                                         contain a `name` field.
        :return: True if successful.
        :raises HTTPError: As raised by requests.Response.raise_for_status().
        """
        if not "name" in atlas_cluster:
            LOG.error("Cannot delete cluster without a name in the meta data!")
            return False

        name = atlas_cluster["name"]
        LOG.info("Shutting down Atlas cluster: %s...", name)
        if self.atlas_client.delete_cluster(name):
            LOG.info("Shutting down Atlas cluster: %s succeeded.", name)
            # Bookkeeping: delete this cluster from `mongodb_setup.out.atlas.clusters`
            self._remove_cluster_from_list(atlas_cluster)
            LOG.debug(self.mongodb_setup["out"])
            self.config.save()
            return True

        # else:
        LOG.error("Shutting down Atlas cluster: %s FAILED.", name)
        return False

    def _remove_cluster_from_list(self, atlas_cluster):
        found = False
        clusters = copy.copy(self.mongodb_setup["out"]["atlas"]["clusters"])
        for i, cluster in enumerate(self.mongodb_setup["out"]["atlas"]["clusters"]):
            if cluster["name"] == atlas_cluster["name"]:
                del clusters[i]
                found = True
        if not found:
            raise LookupError("Didn't find a cluster with name = {}".format(atlas_cluster["name"]))
        self.mongodb_setup["out"]["atlas"]["clusters"] = clusters

    def _find_cluster_in_list(self, atlas_cluster):
        name = atlas_cluster["name"]
        for index, cluster in enumerate(self.mongodb_setup["out"]["atlas"]["clusters"]):
            if cluster["name"] == name:
                return index
        return None


def parse_command_line():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Start a MongoDB cluster in Atlas')
    parser.add_argument('-d', '--debug', action='store_true', help='enable debug output')
    parser.add_argument('--log-file', help='path to log file')

    return parser.parse_args()


def main():
    """ Handle the main functionality (parse args /setup logging ) and then start the mongodb
    cluster."""
    args = parse_command_line()
    log.setup_logging(args.debug, args.log_file)
    LOG.info("atlas_setup.py start")

    config = common.config.ConfigDict('mongodb_setup')
    config.load()

    # start a mongodb configuration using config
    atlas = AtlasSetup(config)
    if atlas.start():
        LOG.info("atlas_setup.py end -- AtlasSetup.start() success")
        return 0

    LOG.info("atlas_setup.py end -- AtlasSetup.start() failed")
    return 1


if __name__ == '__main__':
    sys.exit(main())

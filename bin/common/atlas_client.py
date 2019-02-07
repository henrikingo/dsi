#!/usr/bin/env python2.7
"""
A thin client around Atlas REST API calls we use.

Not complete, rather add calls as you need them.
"""

import time

import requests
import requests.auth as auth
import structlog

LOG = structlog.get_logger(__name__)

DEFAULT_ROOT_URL = "https://cloud.mongodb.com/api/atlas/v1.0/"


class AtlasClient(object):
    """
    A thin client around Atlas REST API calls we use.

    TODO: Especially for delete of cluster, would be nice to support retries on http/network failure

    :raises HTTPError: As raised by requests.Response.raise_for_status()
    """

    def __init__(self, configuration, credentials):
        """
        Initiate an object with configuration and credentials.

        The initialized client will then operate within the given Atlas group, and the given user.
        Other than this, it is stateless: methods are merely HTTP wrappers.

        Note: credentials passed in as a separate object to keep them from being accidentally
        dumped to logs.

        :param dict configuration: group_id (required) and api root url (optional)
        :param dict credentials: user and key (required)
        """
        self.group_id = configuration["group_id"]
        self.root = configuration.get("root", DEFAULT_ROOT_URL)
        self.root += "/" if self.root[-1] != "/" else ""

        # Check and fail early if credentials missing
        assert credentials["user"]
        assert credentials["key"]
        self.auth = auth.HTTPDigestAuth(credentials["user"], credentials["key"])

    def create_cluster(self, configuration):
        """
        Create new Atlas cluster using `configuration` as the request body.

        `POST groups/{GROUP-ID}/clusters`

        https://docs.atlas.mongodb.com/reference/api/clusters-create-one/

        :param dict configuration: Dictionary to use as json request body.
        :return: Response object as dictionary.
        """
        url = "{}groups/{}/clusters".format(self.root, self.group_id)
        response = requests.post(url, json=configuration, auth=self.auth)
        LOG.debug(
            "Create cluster response", headers=response.request.headers, body=response.request.body)
        if not response.ok:
            LOG.error("HTTP error in create_cluster", response=response.json())
            response.raise_for_status()
        else:
            return response.json()

    def get_one_cluster(self, cluster_name):
        """
        Get status for cluster_name.

        `GET groups/{GROUP-ID}/clusters/{CLUSTER-NAME}`

        https://docs.atlas.mongodb.com/reference/api/clusters-get-one/

        :param str cluster_name: The Atlas CLUSTER-NAME in GROUP-ID from init.
        :return: The Atlas response, which contains state and meta-data about the cluster.
        """
        url = "{}groups/{}/clusters/{}".format(self.root, self.group_id, cluster_name)
        response = requests.get(url, auth=self.auth)
        LOG.debug("Get one cluster", headers=response.request.headers)
        if not response.ok:
            LOG.error("HTTP error in get_one_cluster", response=response.json())
            response.raise_for_status()
        else:
            return response.json()

    def await(self, cluster_name):
        """
        Wait until cluster creation is considered finished.

        Current implementation is to wait for status == IDLE.

        :param str cluster_name: The Atlas CLUSTER-NAME in GROUP-ID from init.
        :return: The Atlas response, which contains state and meta-data about the cluster.
        """
        return self.await_state(cluster_name, "IDLE")

    def await_state(self, cluster_name, target_state):
        """
        Periodically poll cluster_name. Return when stateName == target_state.

        TODO: Add a timeout.

        :param str cluster_name: The Atlas CLUSTER-NAME in GROUP-ID from init.
        :param str target_state: The Atlas stateName to wait for. Ex: "IDLE".
        :return: The Atlas response, which contains state and meta-data about the cluster.
        """
        while True:
            # The await state occassionaly fails it's query, particularly in cluster types that take
            # longer to spawn (e.g., NVMe).
            try:
                cluster = self.get_one_cluster(cluster_name)
                LOG.info(
                    "Await state",
                    cluster_name=cluster_name,
                    status=cluster["stateName"],
                    target_state=target_state)
                if cluster["stateName"] == target_state:
                    return cluster
            except requests.exceptions.HTTPError:
                LOG.exception(
                    "In await state and self.get_one_cluster threw. Catching and moving on")
            time.sleep(30)

    def delete_cluster(self, cluster_name):
        """
        Delete a cluster with the given cluster_name.

        DELETE groups/{GROUP-ID}/clusters/{CLUSTER-NAME}

        https://docs.atlas.mongodb.com/reference/api/clusters-delete-one/

        :param str cluster_name: The Atlas CLUSTER-NAME in GROUP-ID from init.
        :return: The Atlas response, which contains state and meta-data about the cluster.
        """
        url = "{}groups/{}/clusters/{}".format(self.root, self.group_id, cluster_name)
        response = requests.delete(url, auth=self.auth)
        LOG.debug("Delete cluster", headers=response.request.headers)
        if not response.ok:
            LOG.error("HTTP error in delete_cluster", response=response.json())
            response.raise_for_status()
        else:
            return True

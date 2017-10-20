#!/usr/bin/env python2.7
''' Create bash output that can be sourced to set environmental variables '''

from __future__ import print_function

import os

import alias

from common.config import ConfigDict


def main():
    ''' Main '''
    conf = ConfigDict('test_control')  #What should the argument be?
    conf.load()
    ssh_key_file = conf['infrastructure_provisioning']['tfvars']['ssh_key_file']
    ssh_key_file = os.path.expanduser(ssh_key_file)
    print('export PEMFILE={0}'.format(ssh_key_file))
    print('export SSHUSER={0}'.format(conf['infrastructure_provisioning']['tfvars']['ssh_user']))
    expanded = alias.expand('workload_client')
    unaliased = alias.unalias(expanded)
    ip_address = alias.lookup_host(unaliased, conf)

    print('export workload_client={0}'.format(ip_address))


if __name__ == '__main__':
    main()

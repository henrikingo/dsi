#!/usr/bin/env python2.8

''' Create bash output that can be sourced to set environmental variables '''

from __future__ import print_function

from common.config import ConfigDict # pylint: disable=relative-import

def main():
    ''' Main '''
    conf = ConfigDict('test_control') #What should the argument be?
    conf.load()
    print('export PEMFILE={0}'.format(conf['infrastructure_provisioning']['tfvars']
                                      ['ssh_key_file']))
    print('export SSHUSER={0}'.format(conf['infrastructure_provisioning']['tfvars']['ssh_user']))

if __name__ == '__main__':
    main()

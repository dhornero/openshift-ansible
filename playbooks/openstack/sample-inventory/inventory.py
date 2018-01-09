#!/usr/bin/env python
"""
This is an Ansible dynamic inventory for OpenStack.

It requires your OpenStack credentials to be set in clouds.yaml or your shell
environment.

"""

from __future__ import print_function

from collections import Mapping
import json

import shade


def build_inventory():
    '''Build the dynamic inventory.'''
    cloud = shade.openstack_cloud()

    inventory = {}

    # TODO(shadower): filter the servers based on the `OPENSHIFT_CLUSTER`
    # environment variable.
    cluster_hosts = [
        server for server in cloud.list_servers()
        if 'metadata' in server and 'clusterid' in server.metadata]

    masters = [server.name for server in cluster_hosts
               if server.metadata['host-type'] == 'master']

    etcd = [server.name for server in cluster_hosts
            if server.metadata['host-type'] == 'etcd']
    if not etcd:
        etcd = masters

    infra_hosts = [server.name for server in cluster_hosts
                   if server.metadata['host-type'] == 'node' and
                   server.metadata['sub-host-type'] == 'infra']

    app = [server.name for server in cluster_hosts
           if server.metadata['host-type'] == 'node' and
           server.metadata['sub-host-type'] == 'app']

    cns = [server.name for server in cluster_hosts
           if server.metadata['host-type'] == 'cns']

    nodes = list(set(masters + infra_hosts + app + cns))

    dns = [server.name for server in cluster_hosts
           if server.metadata['host-type'] == 'dns']

    load_balancers = [server.name for server in cluster_hosts
                      if server.metadata['host-type'] == 'lb']

    osev3 = list(set(nodes + etcd + load_balancers))

    inventory['cluster_hosts'] = {'hosts': [s.name for s in cluster_hosts]}
    inventory['OSEv3'] = {'hosts': osev3}
    inventory['masters'] = {'hosts': masters}
    inventory['etcd'] = {'hosts': etcd}
    inventory['nodes'] = {'hosts': nodes}
    inventory['infra_hosts'] = {'hosts': infra_hosts}
    inventory['app'] = {'hosts': app}
    inventory['glusterfs'] = {'hosts': cns}
    inventory['dns'] = {'hosts': dns}
    inventory['lb'] = {'hosts': load_balancers}

    for server in cluster_hosts:
        if 'group' in server.metadata:
            group = server.metadata.group
            if group not in inventory:
                inventory[group] = {'hosts': []}
            inventory[group]['hosts'].append(server.name)

    inventory['_meta'] = {'hostvars': {}}

    for server in cluster_hosts:
        ssh_ip_address = server.public_v4 or server.private_v4
        hostvars = {
            'ansible_host': ssh_ip_address
        }

        public_v4 = server.public_v4 or server.private_v4
        if public_v4:
            hostvars['public_v4'] = server.public_v4
            hostvars['openshift_public_ip'] = server.public_v4
        # TODO(shadower): what about multiple networks?
        if server.private_v4:
            hostvars['private_v4'] = server.private_v4
            # NOTE(shadower): Yes, we set both hostname and IP to the private
            # IP address for each node. OpenStack doesn't resolve nodes by
            # name at all, so using a hostname here would require an internal
            # DNS which would complicate the setup and potentially introduce
            # performance issues.
            hostvars['openshift_ip'] = server.private_v4
            hostvars['openshift_hostname'] = server.private_v4
        hostvars['openshift_public_hostname'] = server.name

        if server.metadata['host-type'] == 'cns':
            hostvars['glusterfs_devices'] = ['/dev/nvme0n1']

        node_labels = server.metadata.get('node_labels')
        # NOTE(shadower): the node_labels value must be a dict not string
        if not isinstance(node_labels, Mapping):
            node_labels = json.loads(node_labels)

        if node_labels:
            hostvars['openshift_node_labels'] = node_labels

        inventory['_meta']['hostvars'][server.name] = hostvars
    return inventory


if __name__ == '__main__':
    print(json.dumps(build_inventory(), indent=4, sort_keys=True))

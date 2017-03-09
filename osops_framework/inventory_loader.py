
import os
import sys
import json
from collections import defaultdict

class osa(object):

    def __init__(self, inventory):
        with open(inventory, 'r') as f:
            raw_inv=f.read()
        self.data=json.loads(raw_inv)

    def host_meta(self, host=None):
        if host is None:
            meta=self.data['_meta']['hostvars']
        elif host is not None:
            meta=self.data['_meta']['hostvars'].get(host)
            return meta
        hosts=[]
        for k, v in meta.items():
            hosts.append((k,v))
        return hosts


    def baremetal(self):
        hosts=self.host_meta()
        host_list=[]
        for name,meta in hosts:
            if meta.get('is_metal', False) is True:
                host_dict={}
                host_dict['name']=name
                host_dict['ip_address']=meta['ansible_ssh_host']
                host_dict['device_type']='baremetal'
                host_dict['physical_host']=None
                host_dict['service']=meta['component']
                host_dict['parent_id']=None
                host_list.append(host_dict)
        return host_list

    def containers(self):
        hosts=self.host_meta()
        host_list=[]
        for name,meta in hosts:
            if meta.get('is_metal', False) is False:
                host_dict = {}
                host_dict['name']=name
                host_dict['ip_address']=meta['ansible_ssh_host']
                host_dict['device_type']='container'
                host_dict['physical_host']=meta['physical_host']
                host_dict['service']=meta['component']
                host_dict['parent_id']=None
                host_list.append(host_dict)
        return host_list

    def get_host(self, host):
        name=host.get('name')
        meta=self.host_meta(name)
        host_dict = {}
        host_dict['name']=name
        host_dict['ip_address']=meta['ansible_ssh_host']
        host_dict['device_type']='container'
        host_dict['physical_host']=meta['physical_host']
        host_dict['service']=meta['component']
        host_dict['parent_id']=None
        return host_dict


    def variables(self, host):
        hname = host.get('name')
        hid = host.get('id')
        var_data = self.data['_meta']['hostvars'].get(hname, None)
        return var_data

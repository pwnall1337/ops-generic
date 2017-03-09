#!/usr/bin/env python

import os
import sys
import json 
import requests
import argparse
import time
import logging

#quick fixup for testin script until 
#setup.py issues are resolved
sys.path.append('../../')
from osops_common import craton
from osops_common import inventory_loader
from osops_common import daemon

class loader(object):
    def __init__(self, cloud, region, invfile):
        self.auth={}
        self.auth['X-Auth-User']=os.environ['OS_USERNAME']
        self.auth['X-Auth-Project']=os.environ['OS_PROJECT_ID']
        self.auth['X-Auth-Token']=os.environ['OS_PASSWORD']
        self.auth['craton_url']=os.environ['CRATON_URL']
        self.cloud = int(cloud)
        self.region = int(region)
        self.craton = craton.craton_init(self.auth, self.cloud, self.region)
        self.craton.test_auth()
        self.inv=inventory_loader.osa(invfile)
        self.baremetal=self.inv.baremetal()
        self.containers=self.inv.containers()
        self.all_hosts=self.baremetal + self.containers

    def import_hosts(self):
        self.craton.bulk_import(self.baremetal)
        containers=self.craton.get_parents(self.containers)
        self.craton.bulk_import(containers)
        upstream_servers=self.craton.hosts('list')
        inv_host_list=[s['name'] for s in self.all_hosts]
        hosts=[s for s in upstream_servers if s['name'] in inv_host_list]
        for host in hosts:
            try:
                s=self.inv.get_host(host)
                data={}
                data['var_data']=self.inv.variables(host)
                data['var_type']='host'
                data['item_id']=host['id']           
                self.craton.vars('update', data=data)
            except(IndexError):
                print("""\nUpstream host %s not in inventory file. """
                        """Skipping vars for host.\n""" % host['name'])
        for host in hosts:
            try:
                s=self.inv.get_host(host)
                if host['name'] == s['name']:
                    data={}
                    device_type=s['device_type']
                    service=s['service']
                    data['id']=host['id']
                    labels=[device_type]
                    if service is not None:
                        labels.append(service)
                    data['labels']=labels
                    self.craton.hosts('label', data=data)
            except(IndexError):
                print("""\nUpstream host %s not in inventory file. """
                        """Skipping vars for host.\n""" % host['name'])

    def import_system_facts(self):
        from osops_common import hwinfo
        upstream_servers=self.craton.hosts('list')
        inv_host_list=[s['name'] for s in self.all_hosts]
        hosts=[s for s in upstream_servers if s['name'] in inv_host_list]        
        for host in hosts:
            hname = host.get('name')
            hip = host.get('ip_address')
            hid = host.get('id')
            try:
                if 'container' in hname:
                    print("""\nSkipping %s. System facts not supported for """ 
                          """containers. Importing ansible facts instead."""
                          % hname)
                    system_data=hwinfo.load(hip)
                    var_data=system_data.raw_ansible()
                    data={}
                    data['var_data']=var_data
                    data['var_type']='host'
                    data['item_id']=host['id']
                    self.craton.vars('update', data=data)
                else:
                    system_data=hwinfo.load(hip)
                    var_data=system_data.get_all_facts()
                    data={}
                    data['var_data']=var_data
                    data['var_type']='host'          
                    data['item_id']=host['id']         
                    self.craton.vars('update', data=data)
            except(IndexError):
                print("""Connection to host %s failed. Check Connection."""
                      % hname)

class app(daemon.Daemon):

    def run(self, args, s=360):
        invfile=args.get('invfile')
        cloud=args.get('cloud')
        region=args.get('region')
        system_facts=args.get('system_facts')
        try:
            while True:
                obj=loader(cloud, region, invfile)
                obj.import_hosts()
                if system_facts:
                    obj.import_system_facts()
                print('\nData Synced. Sleeping for %s seconds.\n' % s)
                sys.stdout.flush()
                time.sleep(s)
        except(SystemExit,KeyboardInterrupt):
            # Normal exit getting a signal from the parent process
            pass
        except(Exception), e:
            # Something unexpected happened? 
            print('Exception Occurred: %s' % e)
        finally:
            print('Shutting Down')
    
if __name__ == '__main__':


    #check for environment vars
    try:
        os.environ['OS_USERNAME']
        os.environ['OS_PASSWORD']
        os.environ['CRATON_URL']
        os.environ['OS_PROJECT_ID']
    except KeyError:
        print """

 Please source your craton RC file first. 

 The following OS variables are missing:

 OS_USERNAME
 OS_PASWORD
 OS_PROJECT_ID
 CRATON_URL
                
"""
        sys.exit()


    #call argparse
    parser = argparse.ArgumentParser(description="""Import OSA iventory into
                                    Craton.""")
    parser.add_argument('--inventory', help='--inventory inventory file.',
                        required=True)
    parser.add_argument('--cloud', help='--cloud <cloud_id> (int)',
                        required=True)
    parser.add_argument('--region', help='--region <region_id> (int).',
                        required=True)
    parser.add_argument('--daemon', help='Run as a daemon',
                        action='store_true')
#    parser.add_argument('--delete', help='Delete all hosts from Craton.',
#                        action='store_true')
    parser.add_argument('--system-facts', help='Gather ansible host facts.',
                        action='store_true')    
    args = parser.parse_args()
    cloud = args.cloud
    region = args.region
    invfile = args.inventory
    host_import = True
    daemon = args.daemon
    truncate = False
    system_facts = args.system_facts

    if host_import and truncate:
        print('Please only choose one action at a time.')
        sys.exit()
    if host_import is False and truncate is False:
        print('No action was provided. Plase specify --load or --truncate')
        sys.exit()

    if daemon:
        from osops_common import daemon
        pidf='/tmp/craton_loader.pid'
        stdin='/dev/null'
        stdout='/tmp/craton_loader.log'
        stderr='/tmp/craton_loader.log'
        args={}
        args['invfile']=invfile
        args['cloud']=cloud
        args['region']=region
        args['system_facts']=system_facts
        proc=app(pidf, stdin, stdout, stderr)
        proc.daemonize()
        proc.run(args)
    else:
        obj=loader(cloud, region, invfile)
        obj.import_hosts()
        if system_facts:
            obj.import_system_facts()


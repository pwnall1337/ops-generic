
import os
import sys
import json
import requests
import time

class missingkey(Exception):
    def __init__(self, key):
        msg = ('required: %s not provided in data dictionary.' % key)
        print msg

class invalidaction(Exception):
    def __init__(self, action):
        msg = ('Action: %s is not available.' % action)
        print msg

class craton_init(object):

    def __init__(self, auth, cloud, region):
        if not isinstance(auth, dict):
            print('auth must be a dict')
            sys.exit()
        self.headers = auth
        self.region = int(region)
        self.cloud = int(cloud)
        self.headers['Content-type'] = 'application/json'
        self.craton = self.headers.get('craton_url', None)
        if self.craton is None:
            print('Craton URL not found')
            sys.exit()

    def test_auth(self):
        url = self.headers['craton_url']
        r = requests.get(url=url, headers=self.headers)
        if r.status_code == 401:
            sys.exit('\nAuth failed. Pleased verify credentials.\n')

    def action_status(self, s, item, entity=None, resp=None):
        if entity is not None:
            item=('%s, %s' % (item, str(entity)))
        if s == 200:
            msg = ('Action for item %s was successful.' % item)
        elif s == 201:
            msg = ('Create action for item %s was successful.' % item)
        elif s == 204:
            msg = ('Delete action for item %s was successful.' % item)
        elif s == 401:
            msg = ('Action failed for item %s. 401 Not Authorized.' % item)
        elif s == 409:
            msg = ('Action for item %s failed (Duplicate entry).' % item)
        else:
            msg = ('Action for item %s has failed (Unknown reason). \n%s' 
                    % (item, resp))
        return msg

    def make_request(self, endpoint, method=None, data=None, next_link=None):
        #replace this later with an exception class.
        msg = ("\nOops, something went wrong. Is Craton API up?\n")
        if 'GET' in method:
            url = ('%s/%s' % (self.craton, endpoint))
            try:
                if next_link is None:
                    r = requests.get(
                        url = url,
                        headers=self.headers
                        )
                elif next_link is not None:
                    url = (next_link)
                    r = requests.get(
                        url = url,
                        headers=self.headers
                        )
            except:
                sys.exit(msg)
        elif 'DELETE' in method:
            url = ('%s/%s' % (self.craton, endpoint))
            try:
                r = requests.delete(
                    url = url,
                    headers=self.headers
                    )
            except:
                sys.exit(msg)
        elif 'POST' in method:
            url = ('%s/%s' % (self.craton, endpoint))
            try:
                r = requests.post(
                    url = url,
                    data=json.dumps(data),
                    headers=self.headers
                    )
            except:
                sys.exit(msg)
        elif 'PUT' in method:
            url = ('%s/%s' % (self.craton, endpoint))
            try:
                r = requests.put(
                    url = url,
                    data=json.dumps(data),
                    headers=self.headers
                    )
            except:
                sys.exit(msg)
        else:
            raise invalidaction(method)
        status = self.action_status(r.status_code, endpoint, data, r.text)
        print status
        return r.text

    def get_entitys(self, endpoint):
        method = 'GET'
        data = None
        next_link = None
        data_list = []
        while True:
            #Sleep 1 second to not overwhelm Craton API.
            time.sleep(1)
            data = json.loads(self.make_request(endpoint, method, data, next_link))
            try:
                next_link = [s for s in data.get('links', None) if 'next' in s.get('rel',
                                None)][0].get('href')
            except IndexError:
                break
            for k,v in data.items():
                for item in v:
                    if item.get('id', None) is not None:
                        data_list.append(item)
        return data_list
   
    def hosts(self, action, limit='100', **kwargs):
        data = kwargs.get('data', None)
        if data is not None:
            #let's assume user provided a string. Craton api is picky.
            for k,v in data.items():
                if 'id' in k and v is not None:
                    data[k]=int(v)
            host_id=data.get('id', None)
            cell_id=data.get('cell_id', None)
        if 'list' in action:
            endpoint=('hosts?limit=%s' % limit)
            data=self.get_entitys(endpoint)
        elif 'show' in action:
            if host_id is None:
                raise missingkey('id')
            endpoint=('hosts/%s' % host_id)
            method='GET'
            data=self.make_request(endpoint, method)
        elif 'create' in action:
            if data is None:
                sys.exit('required: data type dict argument not provided')
            request_data={}
            request_data['name']=data['name']
            request_data['ip_address']=data['ip_address']
            request_data['device_type']=data['device_type']
            parent_id=data.get('parent_id', None)
            if parent_id is not None:
                request_data['parent_id']=data['parent_id']
            request_data['region_id']=self.region
            request_data['cloud_id']=self.cloud
            if cell_id is not None:
                request_data['cell_id']=cell_id
            method='POST'
            endpoint = ('hosts')
            self.make_request(endpoint, method, request_data)
        elif 'update' in action:
            if data is None:
                sys.exit('required: data type dict argument not provided')
            if host_id is None:
                raise missingkey('id')
            method='PUT'
            endpoint = ('hosts/%s' % host_id)
            request_data = {}
            #remove id from data payload
            for k,v in data.items():
                if not k.startswith('id'):
                    request_data[k] = v
        elif 'label' in action:
            if data is None:
                sys.exit('required: data type dict argument not provided')
            labels = data.get('labels', None)
            if host_id is None:
                raise missingkey('id')
            elif not isinstance(labels, list):
                sys.exit('labels are not in list format')
            method='PUT'
            endpoint = ('hosts/%s/labels' % host_id)
            request_data = {}
            request_data['labels'] = data.get('labels')
            self.make_request(endpoint, method, request_data)
        else:
            raise invalidaction(action)
        return data


    def vars(self, action, **kwargs):
        data=kwargs.get('data', None)
        item_id = data.get('item_id', None)
        var_type = data.get('var_type', None)
        if item_id is None:
            raise missingkey('item_id')
        if var_type is None:
            raise missingkey('var_type')
        if 'list' in action:
            method='GET'
            if 'cell' in var_type:
                endpoint = ('cells/%s/variables' % item_id)
            elif 'region' in var_type:
                endpoint = ('regions/%s/variables' % item_id)
            elif 'host' in var_type:
                endpoint = ('hosts/%s/variables' % item_id)
            else:
                sys.exit('Must choose var type: cell/region/host')
            data = self.make_request(endpoint, method)
        elif 'update' in action:
            method='PUT'
            var_data = data.get('var_data', None)
            if var_data is None:
                sys.exit('required: var_data not provided')
            if 'cell' in var_type:
                endpoint = ('cells/%s/variables' % item_id)
            elif 'region' in var_type:
                endpoint = ('regions/%s/variables' % item_id)
            elif 'host' in var_type:
                endpoint = ('hosts/%s/variables' % item_id)
            else:
                sys.exit('Must choose var type: cell/region/host')
            self.make_request(endpoint, method, var_data)
            data = None
        else:
            raise invalidaction(action)
        return data

    def cells(self, action, limit='100', **kwargs):
        data = kwargs.get('data', None)
        if data is not None:
            #let's assume user provided a string. Craton api is picky.
            for k,v in data.items():
                if 'id' in k:
                    data[k] = int(v)
        if 'list' in action:
            endpoint = ('cells?limit=%s' % limit)
            data = self.get_entitys(endpoint)
        elif 'create' in action:
            if data is None:
                sys.exit('required: data type dict argument not provided')
            if data.get('region_id', None) is None:
                raise missingkey('region_id')
            elif data.get('cloud_id',None) is None:
                raise missingkey('cloud_id')
            method='POST'
            endpoint = ('cells')
            self.make_request(endpoint, method, data)
        elif 'update' in action:
            method='PUT'
            if data is None:
                sys.exit('required: data type dict argument not provided')
            cell_id = data.get('id', None)
            if cell_id is None:
                raise missingkey('id')
            endpoint = ('cells/%s' % cell_id)
            for k,v in data.items():
                if not k.startswith('id'):
                    request_data[k] = v
            self.make_request(endpoint, method, request_data)
        else:
            raise invalidaction(action)
        return data

    def regions(self, action, limit='100', **kwargs):
        data = kwargs.get('data', None)
        if data is not None:
            #let's assume user provided a string. Craton api is picky.
            for k,v in data.items():
                if 'id' in k:
                    data[k] = int(v)
        if 'list' in action:
            endpoint = ('regions?limit=%s' % limit)
            data = self.get_entitys(endpoint)
        elif 'create' in action:
            if data is None:
                sys.exit('required: data type dict argument not provided')
            if data.get('cloud_id', None) is None:
                raise missingkey('cloud_id')
            method='POST'
            endpoint = ('regions')
            self.make_request(endpoint, method, data)
        elif 'update' in action:
            method='PUT'
            if data is None:
                sys.exit('required: data type dict argument not provided')
            region_id = data.get('id', None)
            if region_id is None:
                raise missingkey('id')
            endpoint = ('region/%s' % region_id)
            for k,v in data.items():
                if not k.startswith('id'):
                    request_data[k] = v
            self.make_request(endpoint, method, request_data)
        else:
            raise invalidaction(action)
        return data

    def bulk_import(self, data=None):
        if data is None:
            sys.exit('required: data type list argument not provided')
        #filter some data for craton. Only take items from the dinctionary
        #that are required as craton will error if extra values are packed.
        for host in data:
            if host is not None:
                self.hosts('create', data=host)

    def get_parents(self, data):
        c_list=[]
        if data is None:
            sys.exit('required: data type list argument not provided')
        devices=self.hosts('list')
        d=[s for s in devices if 'baremetal' in s['device_type']]
        for c in data:
            for s in d:
                if c['physical_host'] == s['name']:
                    c['parent_id']=s['id']
                    c_list.append(c)
        return c_list    

import os
import sys
import json
from subprocess import Popen
from subprocess import PIPE

class load(object):

    def __init__(self, host):
        self.host=host
        data=self.get_host_facts()
        self.dmi=data[0]
        self.nics=data[1]
        self.ansible=data[2]

    def proc(self, cmd):
        proc=Popen(cmd, shell=True, stderr=PIPE, stdout=PIPE
                     )
        output=proc.stdout.read()
        err=proc.stderr.read()
        return output, err

    def get_host_facts(self):
        cmd_dmi=('ssh root@%s dmidecode' % self.host)
        cmd_nic=("lspci | egrep -i 'network|ethernet' | cut -d: -f3")
        cmd_ansible=("ansible -i %s, 'all' -m setup" % self.host)
        dmi,err=self.proc(cmd_dmi)
        nics,err=self.proc(cmd_nic)
        try:
            ansible,err=self.proc(cmd_ansible)
        except:
            ansible=None
        return dmi, nics, ansible

    def filter_facts(self, data):
        facts={}
        for k,v in data.items():
            if v is not None:
                facts[k]=v
        return facts

    def parse_dmi_section(self, lines):
        data={
            '_title': lines.next().rstrip(),
            }

        for line in lines:
            line=line.rstrip()
            if line.startswith('\t\t'):
                data[k].append(line.lstrip())
            elif line.startswith('\t'):
                k,v=[i.strip() for i in line.lstrip().split(':', 1)]
                if v:
                    data[k]=v
                else:
                    data[k]=[]
            else:
                break

        return data

    def parse_dmi(self, content):
        TYPE = {
            0:  'bios',
            1:  'system',
            2:  'base board',
            3:  'chassis',
            4:  'processor',
            7:  'cache',
            8:  'port connector',
            9:  'system slot',
            10: 'on board device',
            11: 'OEM strings',
            15: 'system event log',
            16: 'physical memory array',
            17: 'memory device',
            19: 'memory array mapped address',
            24: 'hardware security',
            25: 'system power controls',
            27: 'cooling device',
            32: 'system boot',
            41: 'onboard device',
            }
        data=[]
        lines=iter(content.strip().splitlines())
        while True:
            try:
                line=lines.next()
            except StopIteration:
                break

            if line.startswith('Handle 0x'):
                typ=int(line.split(',', 2)[1].strip()[len('DMI type'):])
                if typ in TYPE:
                    data.append((typ, self.parse_dmi_section(lines)))
        return data

    def parse_hdparm_section(self, lines):
        data={}
        for line in lines:
            line=line.rstrip()
            if line.startswith('\t\t'):
                data[k].append(line.lstrip())
            elif line.startswith('\t'):
                if ':' in line:
                    k,v=[i.strip() for i in line.lstrip().split(':', 1)]
                    if v:
                        data[k]=v
                    else:
                        data[k]=[]
            else:
                break

        return data

    def parse_hdparm(self, content, err=''):
        if err.startswith('SG_IO: bad/missing sense data'):
            data=None
            return data
        data=[]
        lines=iter(content.strip().splitlines())
        while True:
            try:
                line=lines.next()
            except StopIteration:
                break
            if line.startswith(('ATA', 'Configuration')):
                data.append(self.parse_hdparm_section(lines))
        return data

    def get_disk_facts(self):
        disk_facts=[]
        cmd=('ssh root@%s fdisk -l' % self.host)
        out,err=self.proc(cmd)
        data=out.split('\n')
        disks=[s.split()[1].strip(':') for s in data if s.startswith(
                'Disk /dev/') and 'mapper' not in s]
        data_dict={}
        data_dict['system_disks']=disks
        for drive in disks:
            device_name=drive.split('/')[2]
            if not device_name.startswith('s'):
                data_dict[('disk_%s_type' % device_name)]='virtual'
                data_dict[('disk_%s_hdparm' % device_name)]=False
            else:
                cmd=('ssh root@%s hdparm -I %s' % (self.host, drive))
                content,err=self.proc(cmd)
                data=self.parse_hdparm(content,err)
                if data is not None:
                    d=dict(data[0].items() + data[1].items())
                    data_dict[('disk_%s_type' % device_name)]='physical'
                    data_dict[('disk_%s_serial' % device_name)]=d.get(
                               'Serial Number', None)
                    data_dict[('disk_%s_transport' % device_name)]=d.get(
                               'Transport', None)
                    data_dict[('disk_%s_model' % device_name)]=d.get(
                               'Model Number', None)
                    data_dict[('disk_%s_firmware' % device_name)]=d.get(
                               'Firmware Revision', None)
                    data_dict[('disk_%s_speed' % device_name)]=d.get(
                               'Nominal Media Rotation Rate', None)
                    data_dict[('disk_%s_size' % device_name)]=d.get(
                               'device size with M = 1024*1024', None)
                    data_dict[('disk_%s_hdparm' % device_name)]=True
                else:
                    data_dict[('disk_%s_hdparm' % device_name)]=False
        return self.filter_facts(data_dict)

    def raw_dmi(self):
        data=self.parse_dmi(self.dmi)
        return data

    def raw_nics(self):
        data=self.nics.split('\n')
        nics=[]
        for nic in data:
            nic=nic.lstrip()
            if len(nic) >= 2:
                nics.append(nic)
        return nics

    def raw_ansible(self):
        data=self.ansible.split('=>')[1]
        data=json.loads(data)
        data=data['ansible_facts']
        return data

    def bios(self):
        print self.raw_dmi()
        bios_data=[s[1] for s in self.raw_dmi() if s[0] == 0][0]
        data_dict={}
        data_dict['bios_vendor']=bios_data.get('Vendor', None)
        data_dict['bios_version']=bios_data.get('Version', None)
        data_dict['bios_date']=bios_data.get('Release Date', None)
        data_dict['bios_revision']=bios_data.get('BIOS Revision', None)
        return self.filter_facts(data_dict)

    def cpu(self):
        cpu_data=[s[1] for s in self.raw_dmi() if s[0] == 4][0]
        data_dict={}
        data_dict['cpu_cores']=cpu_data.get('Core Count', None)
        data_dict['cpu_speed']=cpu_data.get('Current Speed', None)
        data_dict['cpu_flags']=cpu_data.get('Flags', None)
        data_dict['cpu_type']=cpu_data.get('Version', None)
        data_dict['cpu_manufacturer']=cpu_data.get('Manufacturer', None)
        data_dict['cpu_family']=cpu_data.get('Family', None)
        data_dict['cpu_threads']=cpu_data.get('Thread Count', None)
        return self.filter_facts(data_dict)

    def memory(self):
        mem_data=[s[1] for s in self.raw_dmi() if s[0] == 17][0]
        mem_data_ext=[s[1] for s in self.raw_dmi() if s[0] == 16][0]
        data_dict={}
        data_dict['memory_manufacturer']=mem_data.get('Manufacturer',
                                                      None)
        data_dict['memory_speed']=mem_data.get('Speed', None)
        data_dict['memory_type']=mem_data.get('Type', None)
        data_dict['memory_formfactor']=mem_data.get('Form Factor',
                                                    None)
        data_dict['memory_size']=mem_data.get('Size', None)
        data_dict['memory_dimms']=mem_data_ext.get('Number Of Devices',
                                                   None)
        data_dict['memory_partnumber']=mem_data.get('Part Number',
                                                    None)
        return self.filter_facts(data_dict)

    def system(self):
        system_data=[s[1] for s in self.raw_dmi() if s[0] == 1][0]
        ansible_data=self.raw_ansible()
        data_dict={}
        data_dict['system_manufacturer']=system_data.get('Manufacturer', None)
        data_dict['system_product']=system_data.get('Product Name', None)
        data_dict['system_serial']=system_data.get('Serial Number', None)
        data_dict['system_tag']=system_data.get('Asset Tag', None)
        data_dict['system_os']=ansible_data['ansible_lsb'].get('description', None)
        data_dict['system_os_version']=ansible_data.get('ansible_distribution_version', None)
        data_dict['system_interfaces']=ansible_data.get('ansible_interfaces', None)
        data_dict['system_nics']=self.raw_nics()
        data_dict['system_kernel']=ansible_data.get('ansible_kernel', None)
        pkg_mgr=ansible_data.get('ansible_pkg_mgr', None)
        data_dict['system_pkg_manager']=pkg_mgr
        data_dict['system_packages']=self.get_packages(pkg_mgr)
        return self.filter_facts(data_dict)

    def get_packages(self, pkg_mgr=None):
        if pkg_mgr is None:
            data=None
            return data
        elif 'apt' in pkg_mgr:
            cmd,err=self.proc('dpkg -l')
            data=[s.split()[1] for s in cmd.split('\n') if s.startswith('ii')]
        elif 'yum' in pkg_mgr:
            cmd,err=self.proc('yum list')
            data=cmd
            #to be continue with yum dev box.
        else:
            data=None
        return data

    def get_all_facts(self):
        disk=self.get_disk_facts()
        bios=self.bios()
        cpu=self.cpu()
        mem=self.memory()
        sys=self.system()
        facts=dict(disk.items() + bios.items() + cpu.items() + mem.items() +
                   sys.items())
        return facts


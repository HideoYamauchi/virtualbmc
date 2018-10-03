#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import time
import platform
import re
import subprocess
import shlex
import xml.etree.ElementTree as ET

import pyghmi.ipmi.bmc as bmc

from virtualbmc import log
from virtualbmc import utils
from virtualbmc import exception

LOG = log.get_logger()

# Power states
POWEROFF = 0
POWERON = 1

# Boot device maps
GET_BOOT_DEVICES_MAP = {
    'network': 4,
    'hd': 8,
    'cdrom': 0x14,
}

SET_BOOT_DEVICES_MAP = {
    'network': 'network',
    'hd': 'hd',
    'optical': 'cdrom',
}

class VirtualBMC(bmc.Bmc):

    def __init__(self, username, password, port, address,
                 domain_name, libvirt_uri, libvirt_sasl_username=None,
                 libvirt_sasl_password=None):
        super(VirtualBMC, self).__init__({username: password},
                                         port=port, address=address)
        self.domain_name = domain_name
        self._conn_args = {'uri': libvirt_uri,
                           'sasl_username': libvirt_sasl_username,
                           'sasl_password': libvirt_sasl_password}

    def run_command(self, command):
        process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        status = process.wait()
        (out, err) = process.communicate()
        return status, out, err

    def vbox_cmdline(self, options):
        system = platform.system()
        # Linux and Darwin should work with PATH
        vboxmanage_path = 'VBoxManage'
        if system == 'Windows':
            vboxmanage_path = 'c:/Program Files/Oracle/VirtualBox/VBoxManage.exe'
        return vboxmanage_path + " " + options

    def get_list_vms(self):
        result = {}
        regex = re.compile(r'^\"(.*)\" \{(.*)\}$')

        status, out, err = self.run_command(self.vbox_cmdline("list vms"))
        for line in out.splitlines():
            dom = regex.search(line)
            if dom is not None:
                result[dom.group(1)] = POWEROFF

        status, out, err = self.run_command(self.vbox_cmdline("list runningvms"))
        for line in out.splitlines():
            dom = regex.search(line)
            if dom is not None:
                result[dom.group(1)] = POWERON

        return result

    def get_power_state(self):
        LOG.debug('Get power state called for domain %s', self.domain_name)
        try:
            vms = self.get_list_vms()
            return vms[self.domain_name]
        except Exception as e:
            LOG.error('Error getting the power state of domain %(domain)s. '
                      'Error: %(error)s', {'domain': self.domain_name,
                                           'error': e})
            # Command not supported in present state
            return 0xd5

    def power_off(self):
        LOG.debug('Power off called for domain %s', self.domain_name)
        try:
            status, out, err = self.run_command(self.vbox_cmdline("controlvm " + self.domain_name + " poweroff"))
        except Exception as e:
            LOG.error('Error powering off the domain %(domain)s. '
                      'Error: %(error)s' % {'domain': self.domain_name,
                                            'error': e})
            # Command not supported in present state
            return 0xd5

    def power_on(self):
        LOG.debug('Power on called for domain %s', self.domain_name)
        try:
            status, out, err = self.run_command(self.vbox_cmdline("startvm " + self.domain_name + " --type headless"))
        except Exception as e:
            LOG.error('Error powering off the domain %(domain)s. '
                      'Error: %(error)s' % {'domain': self.domain_name,
                                            'error': e})
            # Command not supported in present state
            return 0xd5

    '''
    def power_cycle(self):
        LOG.debug('Power cycle called for domain %s', self.domain_name)
        try:
            with utils.libvirt_open(**self._conn_args) as conn:
                domain = utils.get_libvirt_domain(conn, self.domain_name)
                if domain.isActive():
                    domain.destroy()
                time.sleep(1)
                domain.create()
        except libvirt.libvirtError as e:
            LOG.error('Error power cycle the domain %(domain)s. '
                      'Error: %(error)s' % {'domain': self.domain_name,
                                            'error': e})
            # Command not supported in present state
            return 0xd5

    def power_reset(self):
        LOG.debug('Power reset called for domain %s', self.domain_name)
        try:
            with utils.libvirt_open(**self._conn_args) as conn:
                domain = utils.get_libvirt_domain(conn, self.domain_name)
                if domain.isActive():
                    domain.reset()
        except libvirt.libvirtError as e:
            LOG.error('Error power reset the domain %(domain)s. '
                      'Error: %(error)s' % {'domain': self.domain_name,
                                            'error': e})
            # Command not supported in present state
            return 0xd5
    '''

    def power_shutdown(self):
        LOG.debug('Soft power off called for domain %s', self.domain_name)
        try:
            status, out, err = self.run_command(self.vbox_cmdline("controlvm " + self.domain_name + " acpipowerbutton"))
        except Exception as e:
            LOG.error('Error powering off the domain %(domain)s. '
                      'Error: %(error)s' % {'domain': self.domain_name,
                                            'error': e})
            # Command not supported in present state
            return 0xd5

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

import os
import platform
import re
import subprocess
import shlex
import sys
import xml.etree.ElementTree as ET

import pyghmi.ipmi.bmc as bmc

from virtualbmc import exception
from virtualbmc import log
from virtualbmc import utils

LOG = log.get_logger()

# Power states
POWEROFF = 0
POWERON = 1

# From the IPMI - Intelligent Platform Management Interface Specification
# Second Generation v2.0 Document Revision 1.1 October 1, 2013
# https://www.intel.com/content/dam/www/public/us/en/documents/product-briefs/ipmi-second-gen-interface-spec-v2-rev1-1.pdf
#
# Command failed and can be retried
IPMI_COMMAND_NODE_BUSY = 0xC0
# Invalid data field in request
IPMI_INVALID_DATA = 0xcc


class VBoxVirtualBMC(bmc.Bmc):

    def __init__(self, username, password, port, address,
                 domain_name, libvirt_uri, libvirt_sasl_username=None,
                 libvirt_sasl_password=None, **kwargs):
        super(VBoxVirtualBMC, self).__init__({username: password},
                                         port=port, address=address)
        self.domain_name = domain_name

        # Linux and Darwin should work with PATH
        self.vboxmanage_path = 'VBoxManage' # can be a customized parameter
        self.vboxmanage_cmd = [self.vboxmanage_path]
        system = platform.system()
        if system == 'Windows':
            self.vboxmanage_path = 'c:/Program Files/Oracle/VirtualBox/VBoxManage.exe'

        if libvirt_sasl_username:
            su = 'su'
            if system == 'Linux': # assumes CentOS/RHEL
                su = 'runuser'
            self.vboxmanage_cmd = [su, libvirt_sasl_username, self.vboxmanage_path]

    def run_vboxmanage(self, options):
        process = subprocess.Popen(self.vboxmanage_cmd + shlex.split(options),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        status = process.wait()
        (out, err) = process.communicate()
        return status, out, err

    def get_list_vms(self):
        result = {}
        regex = re.compile(r'^\"(.*)\" \{(.*)\}$')

        status, out, err = self.run_vboxmanage("list vms")
        for line in out.splitlines():
            dom = regex.search(line)
            if dom is not None:
                result[dom.group(1)] = POWEROFF

        status, out, err = self.run_vboxmanage("list runningvms")
        for line in out.splitlines():
            dom = regex.search(line)
            if dom is not None:
                result[dom.group(1)] = POWERON

        return result

    def get_power_state(self):
        LOG.debug('Get power state called for domain %(domain)s',
                  {'domain': self.domain_name})
        try:
            vms = self.get_list_vms()
            return vms[self.domain_name]
        except Exception as e:
            import traceback
            msg = ('Error getting the power state of domain %(domain)s. '
                   'Error: %(type)s: %(error)s' % {'domain': self.domain_name,
                                                   'type': type(e).__name__,
                                                   'error': e})
            LOG.error(msg)
            raise exception.VirtualBMCError(message=msg)

    def power_off(self):
        LOG.debug('Power off called for domain %(domain)s',
                  {'domain': self.domain_name})
        try:
            status, out, err = self.run_vboxmanage("controlvm " + self.domain_name + " poweroff")
        except Exception as e:
            LOG.error('Error powering off the domain %(domain)s. '
                      'Error: %(error)s', {'domain': self.domain_name,
                                           'error': e})
            # Command failed, but let client to retry
            return IPMI_COMMAND_NODE_BUSY

    def power_on(self):
        LOG.debug('Power on called for domain %(domain)s',
                  {'domain': self.domain_name})
        try:
            status, out, err = self.run_vboxmanage("startvm " + self.domain_name + " --type headless")
        except Exception as e:
            LOG.error('Error powering on the domain %(domain)s. '
                      'Error: %(error)s', {'domain': self.domain_name,
                                           'error': e})
            # Command failed, but let client to retry
            return IPMI_COMMAND_NODE_BUSY

    def power_shutdown(self):
        LOG.debug('Soft power off called for domain %(domain)s',
                  {'domain': self.domain_name})
        try:
            status, out, err = self.run_vboxmanage("controlvm " + self.domain_name + " acpipowerbutton")
        except Exception as e:
            LOG.error('Error soft powering off the domain %(domain)s. '
                      'Error: %(error)s', {'domain': self.domain_name,
                                           'error': e})
            # Command failed, but let client to retry
            return IPMI_COMMAND_NODE_BUSY

    def power_reset(self):
        LOG.debug('Power reset called for domain %(domain)s',
                  {'domain': self.domain_name})
        try:
            status, out, err = self.run_vboxmanage("controlvm " + self.domain_name + " reset")
        except Exception as e:
            LOG.error('Error reseting the domain %(domain)s. '
                      'Error: %(error)s', {'domain': self.domain_name,
                                           'error': e})
            # Command not supported in present state
            return IPMI_COMMAND_NODE_BUSY

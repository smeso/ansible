#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2014, Brian Coca <briancoca+ansible@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['stableinterface'],
                    'supported_by': 'core'}

DOCUMENTATION = '''
---
module: debconf
short_description: Configure a .deb package
description:
     - Configure a .deb package using debconf-set-selections. Or just query existing selections.
version_added: "1.6"
notes:
    - This module requires the command line debconf tools.
    - A number of questions have to be answered (depending on the package).
      Use 'debconf-show <package>' on any Debian or derivative with the package
      installed to see questions/settings available.
    - Some distros will always record tasks involving the setting of passwords as changed. This is due to debconf-get-selections masking passwords.
requirements:
  - debconf
  - debconf-utils
  - python-apt (python 2)
  - python3-apt (python 3)
options:
  name:
    description:
      - Name of package to configure.
    required: true
    aliases: [ pkg ]
  question:
    description:
      - A debconf configuration setting.
    aliases: [ selection, setting ]
  vtype:
    description:
      - The type of the value supplied.
      - C(seen) was added in 2.2.
    choices: [ boolean, error, multiselect, note, password, seen, select, string, text, title, text ]
  value:
    description:
      -  Value to set the configuration to.
    aliases: [ answer ]
  unseen:
    description:
      - Do not set 'seen' flag when pre-seeding.
    type: bool
    default: False
  reconfigure:
    description:
      - If the package is already installed it will be reconfigured via 'dpkg-reconfigure'
    type: bool
    default: False
    version_added: "2.7"
author:
- Brian Coca (@bcoca)

'''

EXAMPLES = '''
- name: Set default locale to fr_FR.UTF-8
  debconf:
    name: locales
    question: locales/default_environment_locale
    value: fr_FR.UTF-8
    vtype: select

- name: set to generate locales and regenerate them
  debconf:
    name: locales
    question: locales/locales_to_be_generated
    value: en_US.UTF-8 UTF-8, fr_FR.UTF-8 UTF-8
    vtype: multiselect
    reconfigure: true

- name: Accept oracle license
  debconf:
    name: oracle-java7-installer
    question: shared/accepted-oracle-license-v1-1
    value: 'true'
    vtype: select

- name: Specifying package you can register/return the list of questions and current values
  debconf:
    name: tzdata
'''

import ansible.module_utils.apt_utils as apt_utils

from ansible.module_utils.basic import AnsibleModule


def reconfigure_pkg(apt, module, pkgname):
    cache = apt_utils.get_cache(apt, module)
    pkg = cache[pkgname]
    try:
        installed = pkg.is_installed
    except AttributeError:
        # assume older version of python-apt is installed
        installed = pkg.isInstalled
    if not installed:
        return
    cmd = ' '.join([module.get_bin_path('dpkg-reconfigure', True),
                    '--frontend noninteractive',
                    pkgname])
    rc, msg, err = module.run_command(cmd)
    if rc != 0:
        module.fail_json(msg=err)


def get_selections(module, pkg):
    cmd = [module.get_bin_path('debconf-show', True), pkg]
    rc, out, err = module.run_command(' '.join(cmd))

    if rc != 0:
        module.fail_json(msg=err)

    selections = {}

    for line in out.splitlines():
        (key, value) = line.split(':', 1)
        selections[key.strip('*').strip()] = value.strip()

    return selections


def set_selection(module, pkg, question, vtype, value, unseen):
    setsel = module.get_bin_path('debconf-set-selections', True)
    cmd = [setsel]
    if unseen:
        cmd.append('-u')

    if vtype == 'boolean':
        if value == 'True':
            value = 'true'
        elif value == 'False':
            value = 'false'
    data = ' '.join([pkg, question, vtype, value])

    return module.run_command(cmd, data=data)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True, aliases=['pkg']),
            question=dict(type='str', aliases=['selection', 'setting']),
            vtype=dict(type='str', choices=['boolean', 'error', 'multiselect', 'note', 'password', 'seen', 'select', 'string', 'text', 'title']),
            value=dict(type='str', aliases=['answer']),
            unseen=dict(type='bool'),
            reconfigure=dict(type='bool'),
        ),
        required_together=(['question', 'vtype', 'value'],),
        supports_check_mode=True,
    )

    # TODO: enable passing array of options and/or debconf file from get-selections dump
    pkg = module.params["name"]
    question = module.params["question"]
    vtype = module.params["vtype"]
    value = module.params["value"]
    unseen = module.params["unseen"]
    reconfigure = module.params["reconfigure"]

    if reconfigure:
        apt = apt_utils.import_apt(module)[0]

    prev = get_selections(module, pkg)

    changed = False
    msg = ""

    if question is not None:
        if vtype is None or value is None:
            module.fail_json(msg="when supplying a question you must supply a valid vtype and value")

        if question not in prev or prev[question] != value:
            changed = True

    if changed:
        if not module.check_mode:
            rc, msg, e = set_selection(module, pkg, question, vtype, value, unseen)
            if rc:
                module.fail_json(msg=e)
            elif reconfigure:
                reconfigure_pkg(apt, module, pkg)

        curr = {question: value}
        if question in prev:
            prev = {question: prev[question]}
        else:
            prev[question] = ''
        if module._diff:
            after = prev.copy()
            after.update(curr)
            diff_dict = {'before': prev, 'after': after}
        else:
            diff_dict = {}

        module.exit_json(changed=changed, msg=msg, current=curr, previous=prev, diff=diff_dict)

    module.exit_json(changed=changed, msg=msg, current=prev)


if __name__ == '__main__':
    main()

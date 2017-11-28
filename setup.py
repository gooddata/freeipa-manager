#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2007-2017, GoodData(R) Corporation. All rights reserved

import os
from setuptools import setup


with open('requirements.txt') as deps_file:
    deps = [i.replace('\n', '') for i in deps_file.readlines()]


# Parameters for build
params = {
    'name': 'freeipa-manager',
    'version': '1.%s' % os.environ['CI_VERSION'],
    'packages': ['ipamanager'],
    'entry_points': {
        'console_scripts': [
            'ipamanager=ipamanager.freeipa_manager:main',
            'ipamanager-pull-request=ipamanager.tools.github_forwarder:main']
    },
    'url': 'https://github.com/gooddata/gdc-ipa-utils',
    'license': 'Proprietary',
    'author': 'GoodData Corporation',
    'author_email': 'root@gooddata.com',
    'description': 'FreeIPA Manager',
    'long_description': 'GoodData FreeIPA management tooling',
    'install_requires': deps
}

setup(**params)

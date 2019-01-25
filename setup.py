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
    'version': '%s' % os.environ.get('PACKAGE_VERSION', 'dev'),
    'packages': ['ipamanager', 'ipamanager.tools'],
    'entry_points': {
        'console_scripts': [
            'ipamanager=ipamanager.freeipa_manager:main',
            'ipamanager-pull-request=ipamanager.tools.github_forwarder:main']
    },
    'url': 'https://github.com/gooddata/freeipa-manager',
    'license': 'BSD',
    'author': 'GoodData Corporation',
    'author_email': 'scrum7@gooddata.com',
    'description': 'FreeIPA Manager',
    'long_description': 'FreeIPA entity provisioning tool.',
    'classifiers': [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7'
    ],
    'install_requires': deps
}

setup(**params)

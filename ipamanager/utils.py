#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.
"""
FreeIPA Manager - utility module

Various utility functions for better code readability & organization.
"""

import argparse
import logging
import re
import yaml
from yamllint.config import YamlLintConfig
from yamllint.linter import run as yamllint_check

import entities
from errors import ConfigError


# supported FreeIPA entity types
ENTITY_CLASSES = [
    entities.FreeIPAHBACRule, entities.FreeIPAHBACService,
    entities.FreeIPAHBACServiceGroup, entities.FreeIPAHostGroup,
    entities.FreeIPAPermission, entities.FreeIPAPrivilege,
    entities.FreeIPARole, entities.FreeIPAService,
    entities.FreeIPASudoRule, entities.FreeIPAUser,
    entities.FreeIPAUserGroup
]


def init_logging(loglevel):
    if loglevel == logging.DEBUG:
        fmt = '%(levelname)s:%(name)s:%(lineno)3d:%(funcName)s: %(message)s'
    else:
        fmt = '%(levelname)s:%(name)s: %(message)s'
    logging.basicConfig(level=loglevel, format=fmt)


def init_api_connection(loglevel):
    from ipalib import api
    api.bootstrap(context='cli', verbose=(loglevel == logging.DEBUG))
    api.finalize()
    api.Backend.rpcclient.connect()


def _type_threshold(value):
    try:
        number = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))
    if number < 1 or number > 100:
        raise argparse.ArgumentTypeError('must be a number in range 1-100')
    return number


def _type_verbosity(value):
    return {0: logging.WARNING, 1: logging.INFO}.get(value, logging.DEBUG)


def _args_common():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('config', help='Config repository path')
    common.add_argument('-p', '--pull-types', nargs='+', default=['user'],
                        help='Types of entities to pull')
    common.add_argument('-s', '--settings', help='Settings file')
    common.add_argument('-v', '--verbose', action='count', default=0,
                        dest='loglevel', help='Verbose mode (-vv for debug)')
    return common


def parse_args():
    common = _args_common()

    parser = argparse.ArgumentParser(description='FreeIPA Manager')
    actions = parser.add_subparsers(help='action to execute')

    check = actions.add_parser('check', parents=[common])
    check.set_defaults(action='check')

    diff = actions.add_parser('diff', parents=[common])
    diff.add_argument('sub_path', help='Path to the subtrahend directory')
    diff.set_defaults(action='diff')

    push = actions.add_parser('push', parents=[common])
    push.set_defaults(action='push')
    push.add_argument('-d', '--deletion', action='store_true',
                      help='Enable deletion of entities')
    push.add_argument('-f', '--force', action='store_true',
                      help='Actually make changes (no dry run)')
    push.add_argument('-t', '--threshold', type=_type_threshold,
                      metavar='(%)', help='Change threshold', default=10)

    pull = actions.add_parser('pull', parents=[common])
    pull.set_defaults(action='pull')
    pull.add_argument(
        '-a', '--add-only', action='store_true', help='Add-only mode')
    pull.add_argument(
        '-d', '--dry-run', action='store_true', help='Dry-run mode')

    args = parser.parse_args()
    # type & action cannot be combined in arg constructor, so parse -v here
    args.loglevel = _type_verbosity(args.loglevel)

    # set default settings file based on action
    if not args.settings:
        if args.action in ('diff', 'pull'):
            args.settings = '/opt/freeipa-manager/settings_pull.yaml'
        else:
            args.settings = '/opt/freeipa-manager/settings_push.yaml'
    return args


def run_yamllint_check(data):
    """
    Run a yamllint check on parsed file contents
    to verify that the file syntax is correct.
    :param str data: contents of the configuration file to check
    :param yamllint.config.YamlLintConfig: yamllint config to use
    :raises ConfigError: in case of yamllint errors
    """
    rules = {'extends': 'default', 'rules': {'line-length': 'disable'}}
    lint_errs = list(yamllint_check(data, YamlLintConfig(yaml.dump(rules))))
    if lint_errs:
        raise ConfigError('yamllint errors: %s' % lint_errs)


def check_ignored(entity_class, name, ignored):
    """
    Check if an entity should be ignored based on settings.
    :param object entity_class: entity type
    :param str name: entity name
    :param dict ignored: ignored entity settings
    :returns: True if entity should be ignored, False otherwise
    :rtype: bool
    """
    for pattern in ignored.get(entity_class.entity_name, []):
        if re.match(pattern, name):
            return True
    return False

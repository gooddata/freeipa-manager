#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.
"""
FreeIPA Manager - utility module

Various utility functions for better code readability & organization.
"""

import argcomplete
import argparse
import logging
import logging.handlers
import os
import re
import socket
import sys
import voluptuous
import yaml
from yamllint.config import YamlLintConfig
from yamllint.linter import run as yamllint_check

import entities
from errors import ConfigError
from schemas import schema_settings


# supported FreeIPA entity types
ENTITY_CLASSES = [
    entities.FreeIPAHBACRule, entities.FreeIPAHBACService,
    entities.FreeIPAHBACServiceGroup, entities.FreeIPAHostGroup,
    entities.FreeIPAPermission, entities.FreeIPAPrivilege,
    entities.FreeIPARole, entities.FreeIPAService,
    entities.FreeIPASudoRule, entities.FreeIPAUser,
    entities.FreeIPAUserGroup
]


def _check_handler_present(logger, handler_type, *compare):
    """
    Check if a handler of given and with given attributes
    has been added to the logger already.
    :param logging.Logger logger: logger whose handlers to check
    :param type handler_type: handler class to check for
    :param [(str, obj)] compare:
        list of (attribute, value) items to check the handler against
        (e.g., (stream, sys.stderr) will check if handler.stream == sys.stderr)
    :returns: True if such a handler is configured, False otherwise
    :rtype: bool
    """
    for handler in logger.handlers:
        if isinstance(handler, handler_type):
            attrs_match = True
            for attr, value in compare:
                try:
                    if getattr(handler, attr) != value:
                        attrs_match = False
                        break
                except AttributeError:
                    continue
            if attrs_match:
                return True
    return False


def init_logging(loglevel):
    lg = logging.getLogger()  # add handlers to all loggers
    lg.setLevel(logging.DEBUG)  # higher levels per handler below

    # stderr handler
    if _check_handler_present(
            lg, logging.StreamHandler, ('stream', sys.stderr)):
        lg.debug('Stderr handler already added')
    else:
        if loglevel == logging.DEBUG:
            fm = '%(levelname)s:%(name)s:%(lineno)3d:%(funcName)s: %(message)s'
        else:
            fm = '%(levelname)s:%(name)s: %(message)s'
        handler_stderr = logging.StreamHandler(sys.stderr)
        handler_stderr.setFormatter(logging.Formatter(fmt=fm))
        handler_stderr.setLevel(loglevel)
        lg.addHandler(handler_stderr)
        lg.debug('Stderr handler added to root logger')

    # syslog output handler
    facility = logging.handlers.SysLogHandler.LOG_LOCAL5
    if _check_handler_present(lg, logging.handlers.SysLogHandler,
                              ('facility', facility), ('address', '/dev/log')):
        lg.debug('Syslog handler already added')
    else:
        try:
            handler_syslog = logging.handlers.SysLogHandler(
                address='/dev/log', facility=facility)
            handler_syslog.setFormatter(
                logging.Formatter(fmt='ipamanager: %(message)s'))
            handler_syslog.setLevel(logging.INFO)
            lg.addHandler(handler_syslog)
            lg.debug('Syslog handler added to root logger')
        except socket.error as err:
            lg.error('Syslog connection failed: %s', err)


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
                        help='Types of entities to pull',
                        choices=[cls.entity_name for cls in ENTITY_CLASSES])
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

    template = actions.add_parser('template', parents=[common])
    template.add_argument('template', help='Path to template file')
    template.add_argument(
        '-d', '--dry-run', action='store_true', help='Dry-run mode')
    template.set_defaults(action='template')

    roundtrip = actions.add_parser('roundtrip', parents=[common])
    roundtrip.add_argument(
        '-I', '--no-ignored', action='store_true',
        help='Load all entities (including ignored ones)')
    roundtrip.set_defaults(action='roundtrip')

    argcomplete.autocomplete(parser)
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


def _merge_include(target, source):
    for key, value in source.iteritems():
        if isinstance(value, dict) and key in target:
            target[key].update(value)
        else:
            target[key] = value


def load_settings(path):
    """
    Load the tool settings from the given file.
    If there is an include parameter in the settings file,
    the listed files are included in the config.
    :param str path: path to the settings file
    :returns: loaded settings file
    :rtype: dict
    """
    result = {}
    with open(path) as src:
        raw = src.read()
        run_yamllint_check(raw)
        settings = yaml.safe_load(raw)
    # run validation of parsed YAML against schema
    voluptuous.Schema(schema_settings)(settings)
    subconfigs = []
    for included in settings.pop('include', []):
        subconf = load_settings(os.path.join(os.path.dirname(path), included))
        subconfigs.append(subconf)
    subconfigs.append(settings)
    merge_include = settings.pop('merge_include', False)
    for config in subconfigs:
        if merge_include:
            _merge_include(result, config)
        else:
            result.update(config)
    return result


def check_ignored(entity_class, name, ignored):
    """
    Check if an entity should be ignored based on settings.
    :param object entity_class: entity type
    :param str name: entity name
    :param dict ignored: ignored entity settings
    :returns: True if entity should be ignored, False otherwise
    :rtype: bool
    """
    print(dummy)
    for pattern in ignored.get(entity_class.entity_name, []):
        if re.match(pattern, name):
            return True
    return False


def find_entity(entity_dict, entity_type, name):
    """
    Find an entity by its type and name.
    :param dict entity_dict: dictionary of parsed entities
    :param str entity_name: entity type to search for
    :param str name: entity name to search for
    """
    return entity_dict.get(entity_type, {}).get(name)

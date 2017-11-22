"""
GoodData FreeIPA tooling
Configuration parsing tool

Various utility functions for better code readability & organization.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import argparse
import logging
from yamllint.config import YamlLintConfig
from yamllint.linter import run as yamllint_check

import entities
from errors import ConfigError


# supported FreeIPA entity types
ENTITY_CLASSES = [
    entities.FreeIPAHBACRule, entities.FreeIPAHostGroup,
    entities.FreeIPASudoRule, entities.FreeIPAUser, entities.FreeIPAUserGroup]

# FIXME make long line warning-only (PAAS-12475)
yamllint_config = YamlLintConfig('extends: default')


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
    common.add_argument('-v', '--verbose', action='count', default=0,
                        dest='loglevel', help='Verbose mode (-vv for debug)')
    common.add_argument('-r', '--rules', help='Config check rules file',
                        default='/opt/freeipa-manager/rules.yaml')
    # FIXME ignored entities can be taken from settings file (PAAS-12475)
    common.add_argument('-i', '--ignored', help='Ignored entities file',
                        default='/opt/freeipa-manager/ignored.yaml')
    return common


def _args_pull_common(parents):
    pull_common = argparse.ArgumentParser(add_help=False, parents=parents)
    pull_common.set_defaults(
        action='pull', commit=False, pull_request=False)
    pull_common.add_argument(
        '-a', '--add-only', action='store_true', help='Add-only mode')
    pull_common.add_argument(
        '-d', '--dry-run', action='store_true', help='Dry-run mode')
    pull_common.add_argument(
        '-B', '--base', help='Base branch', default='master')
    pull_common.add_argument(
        '-b', '--branch', help='Branch to commit into (default: generated)')
    return pull_common


def parse_args():
    common = _args_common()
    pull_common = _args_pull_common(parents=[common])

    parser = argparse.ArgumentParser(description='FreeIPA Manager')
    actions = parser.add_subparsers(help='action to execute')

    check = actions.add_parser('check', parents=[common])
    check.set_defaults(action='check')

    push = actions.add_parser('push', parents=[common])
    push.set_defaults(action='push')
    push.add_argument('-d', '--deletion', action='store_true',
                      help='Enable deletion of entities')
    push.add_argument('-f', '--force', action='store_true',
                      help='Actually make changes (no dry run)')
    push.add_argument('-t', '--threshold', type=_type_threshold,
                      metavar='(%)', help='Change threshold', default=10)

    actions.add_parser('pull', parents=[pull_common])
    pull_commit = actions.add_parser('pull-commit', parents=[pull_common])
    pull_commit.set_defaults(commit=True)
    pull_request = actions.add_parser('pull-request', parents=[pull_common])
    pull_request.set_defaults(commit=True, pull_request=True)
    pull_request.add_argument(
        '-o', '--owner', help='Repo owner', default='gooddata')
    pull_request.add_argument(
        '-R', '--repo', help='Repo name', default='freeipa-manager-config')
    pull_request.add_argument('-t', '--token', help='GitHub API token')
    pull_request.add_argument(
        '-u', '--user', help='GitHub user', default='yenkins')

    args = parser.parse_args()
    # type & action cannot be combined in arg constructor, so parse -v here
    args.loglevel = _type_verbosity(args.loglevel)
    return args


def run_yamllint_check(data):
    """
    Run a yamllint check on parsed file contents
    to verify that the file syntax is correct.
    :param str data: contents of the configuration file to check
    :param yamllint.config.YamlLintConfig: yamllint config to use
    :raises ConfigError: in case of yamllint errors
    """
    lint_errs = [err for err in yamllint_check(data, yamllint_config)]
    if lint_errs:
        raise ConfigError('yamllint errors: %s' % lint_errs)

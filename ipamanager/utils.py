"""
GoodData FreeIPA tooling
Configuration parsing tool

Various utility functions for better code readability & organization.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import argparse
import logging

import entities


# supported FreeIPA entity types
ENTITY_CLASSES = [
    entities.FreeIPAHBACRule, entities.FreeIPAHostGroup,
    entities.FreeIPASudoRule, entities.FreeIPAUser, entities.FreeIPAUserGroup]


def init_logging(loglevel):
    if loglevel == logging.DEBUG:
        fmt = '%(levelname)s:%(name)s:%(lineno)3d:%(funcName)s: %(message)s'
    else:
        fmt = '%(levelname)s:%(name)s: %(message)s'
    logging.basicConfig(level=loglevel, format=fmt)


def parse_args():
    parser = argparse.ArgumentParser(description='FreeIPA management CLI tool')
    parser.add_argument('action', choices=['check', 'pull', 'push'])
    parser.add_argument('config', nargs='?', help='Path to config repository',
                        default='/opt/freeipa-manager/entities')
    parser.add_argument('-r', '--rules-file', help='Config check rules file',
                        default='/opt/freeipa-manager/rules.yaml')
    parser.add_argument('-t', '--threshold', type=_type_threshold,
                        metavar='(%)', help='Change threshold', default=20)
    parser.add_argument('-f', '--force', action='store_true',
                        help='Actually make changes (no dry run)')
    parser.add_argument('-d', '--enable-deletion', action='store_true',
                        help='Enable deletion of entities')
    parser.add_argument('-i', '--ignored', help='Ignored entities list file')
    parser.add_argument('-v', '--verbose', dest='debug', action='store_true')
    return parser.parse_args()


def _type_threshold(value):
    try:
        number = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))
    if number < 1 or number > 100:
        raise argparse.ArgumentTypeError('must be a number in range 1-100')
    return number

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
    parser.add_argument('config', help='Path to config repository')
    parser.add_argument('action', choices=['check', 'compare', 'pull', 'push'])
    parser.add_argument('-r', '--rules-file', default='integrity_config.yaml',
                        help='Integrity check rules file')
    parser.add_argument('-d', '--domain', help='LDAP domain',
                        nargs='?', const='intgdc.com', default='localhost')
    parser.add_argument('--dry', help='Dry run')
    parser.add_argument(
        '-v', '--verbose', dest='loglevel', action='store_const',
        const=logging.DEBUG, default=logging.INFO)
    args = parser.parse_args()
    return args

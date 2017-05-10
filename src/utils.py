"""
GoodData FreeIPA tooling
Configuration parsing tool

Various utility functions for better code readability & organization.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import argparse
import logging
import re

import schemas


# supported FreeIPA entity types
ENTITY_TYPES = ['hostgroups', 'users', 'usergroups']
# names of arguments of each entity type (for LDAP search filtering)
ENTITY_ARGS = {
    'hostgroups': schemas.schema_groups[str].keys(),
    'users': schemas.schema_users[str].keys(),
    'usergroups': schemas.schema_groups[str].keys()
}


# base DN of entity type
LDAP_BASE_DN = {
    'hostgroups': 'cn=hostgroups,cn=accounts,dc=intgdc,dc=com',
    'users': 'cn=users,cn=accounts,dc=intgdc,dc=com',
    'usergroups': 'cn=groups,cn=accounts,dc=intgdc,dc=com'
}
# name of entity ID for each entity type
LDAP_ID = {
    'hostgroups': 'cn',
    'users': 'uid',
    'usergroups': 'cn'
}
# attribute name mapping between local configuration and LDAP
LDAP_CONF_MAPPING = {
    'hostgroups': {},
    'users': {
        'emailAddress': 'mail',
        'firstName': 'givenName',
        'lastName': 'sn',
        'organizationUnit': 'ou',
        'githubLogin': 'carLicense',
        'mail': 'emailAddress',
        'givenName': 'firstName',
        'sn': 'lastName',
        'ou': 'organizationUnit',
        'carLicense': 'githubLogin'
    },
    'usergroups': {}
}


def ldap_parse_dn(dn):
    """
    Parse DN into ID name, entity name and base DN.
    A sample DN looks like this:
        - uid=firstname.lastname,cn=users,cn=accounts,dc=intgdc,dc=com
        - cn=group-one,cn=groups,cn=accounts,dc=intgdc,dc=com
    :param str dn: entity DN to parse
    """
    match = re.match(r'(\w+)=([^,]+),(.*)', dn)
    if match:
        return match.groups()
    return (None, None, None)


def ldap_get_dn(entity_type, cn=''):
    """
    Construct entity DN from entity type and entity name.
    :param str entity_type: entity type
    :param str cn: entity name (optional)
    """
    return '%s%s' % (
        '%s=%s,' % (LDAP_ID[entity_type], cn) if cn else '',
        LDAP_BASE_DN[entity_type])


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
    parser.add_argument('-d', '--domain', help='FreeIPA SRV record to resolve',
                        nargs='?', const='intgdc.com')
    parser.add_argument('-t', '--types', nargs='*', choices=ENTITY_TYPES,
                        help='Only process given entity types')
    parser.add_argument('--dry', help='Dry run')
    parser.add_argument(
        '-v', '--verbose', dest='loglevel', action='store_const',
        const=logging.DEBUG, default=logging.INFO)
    args = parser.parse_args()
    args.types = set(args.types) if args.types else ENTITY_TYPES
    return args

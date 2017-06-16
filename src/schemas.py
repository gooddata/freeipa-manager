"""
GoodData FreeIPA tooling
Configuration parsing tool

Validation schemas for FreeIPA entities configuration.

NOTE: 'noldap_'-prefixed attributes are only used internally
      by the script and are not propagated to FreeIPA.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

from voluptuous import Any


schema_users = {
    'emailAddress': str,
    'firstName': str,
    'lastName': str,
    'initials': str,
    'organizationUnit': str,
    'manager': str,
    'githubLogin': str,
    'title': str,
    'memberOf': dict
}


schema_usergroups = {
    'description': str,
    'memberOf': dict
}


schema_hostgroups = {
    'description': str,
    'memberOf': dict
}


schema_hbac = {
    'description': str,
    'enabled': Any('TRUE', 'FALSE'),
    'memberHost': str,
    'memberUser': str
}


schema_sudo = {
    'cmdCategory': str,
    'description': str,
    'enabled': Any('TRUE', 'FALSE'),
    'memberHost': str,
    'memberUser': str,
    'options': [str],
    'runAsGroupCategory': str,
    'runAsUserCategory': str
}

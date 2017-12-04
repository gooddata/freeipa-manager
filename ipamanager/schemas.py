"""
GoodData FreeIPA tooling
Configuration parsing tool

Validation schemas for FreeIPA entities configuration.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

from voluptuous import Any, Required

_name_type = Any(str, unicode)
_item_or_list = Any(str, [str])
_schema_memberof = {str: [str]}


schema_settings = {
    'user-group-pattern': str,
    'ignore': {
        Any('user', 'group', 'hostgroup', 'hbacrule', 'sudorule'): [str]
    },
    'deletion-patterns': [str]
}


schema_users = {
    Required('firstName'): _name_type,
    Required('lastName'): _name_type,
    'initials': str,
    'emailAddress': _item_or_list,
    'organizationUnit': str,
    'manager': str,
    'githubLogin': _item_or_list,
    'title': str,
    'memberOf': _schema_memberof,
    'metaparams': {str: str}
}


schema_usergroups = {
    'description': str,
    'memberOf': _schema_memberof,
    'metaparams': {str: str}
}


schema_hostgroups = {
    'description': str,
    'memberOf': _schema_memberof,
    'metaparams': {str: str}
}


schema_hbac = {
    'description': str,
    'memberHost': [str],
    'memberUser': [str],
    'serviceCategory': 'all',
    'metaparams': {str: str}
}


schema_sudo = {
    'cmdCategory': 'all',
    'description': str,
    'memberHost': [str],
    'memberUser': [str],
    'options': ['!authenticate', '!requiretty'],
    'runAsGroupCategory': 'all',
    'runAsUserCategory': 'all',
    'metaparams': {str: str}
}

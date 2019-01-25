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
        Any('user', 'group', 'hostgroup', 'hbacrule', 'sudorule',
            'role', 'permission', 'privilege', 'service',
            'hbacsvc', 'hbacsvcgroup'): [str]
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
    'posix': bool,
    'metaparams': {str: str}
}


schema_hostgroups = {
    'description': str,
    'memberOf': _schema_memberof,
    'metaparams': {str: str}
}

schema_hbacservices = {
    'description': str,
    'memberOf': _schema_memberof,
    'metaparams': {str: str}
}

schema_hbacsvcgroups = {
    'description': str,
    'metaparams': {str: str}
}

schema_hbac = {
    'description': str,
    'memberHost': [str],
    'memberUser': [str],
    'memberService': [str],
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
    'metaparams`': {str: str}
}


schema_roles = {
    'description': str,
    'memberOf': _schema_memberof,
    'metaparams': {str: str}
}


schema_privileges = {
    'description': str,
    'memberof_permission': _item_or_list,
    'memberOf': _schema_memberof,
    'metaparams': {str: str}
}


schema_permissions = {
    'description': str,
    'subtree': _item_or_list,
    'attributes': _item_or_list,
    'grantedRights': _item_or_list,
    'defaultAttr': _item_or_list,
    'location': _item_or_list,
    'memberOf': _schema_memberof,
    'metaparams': {str: str}
}


schema_services = {
    'managedBy': _item_or_list,
    'memberOf': _schema_memberof,
    'description': str,
    'metaparams': {str: str}
}

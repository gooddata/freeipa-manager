"""
GoodData FreeIPA tooling
Configuration parsing tool

Validation schemas for FreeIPA entities configuration.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

from voluptuous import Required

schema_single_user = {
    Required('emailAddress'): str,
    Required('firstName'): str,
    Required('lastName'): str,
    Required('initials'): str,
    Required('organizationUnit'): str,
    Required('manager'): str,
    'githubLogin': str,
    'title': str,
    'memberOf': [str]
}

schema_users = {
    str: schema_single_user
}

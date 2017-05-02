"""
GoodData FreeIPA tooling
Configuration parsing tool

Validation schemas for FreeIPA entities configuration.

NOTE: 'noldap_'-prefixed attributes are only used internally
      by the script and are not propagated to FreeIPA.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

schema_users = {
    str: {
        'emailAddress': str,
        'firstName': str,
        'lastName': str,
        'initials': str,
        'organizationUnit': str,
        'manager': str,
        'githubLogin': str,
        'title': str,
        'memberOf': {str: [str]}
    }
}

schema_groups = {
    str: {
        'description': str,
        'memberOf': {str: [str]}
    }
}

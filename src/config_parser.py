"""
GoodData FreeIPA tooling
Configuration parsing tool

Tools for validating & parsing the FreeIPA
configuration for hosts, users & groups.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import voluptuous

from core import FreeIPAManagerCore
from entities import FreeIPAUser
from errors import ConfigError
from schemas import schema_users


class ConfigParser(FreeIPAManagerCore):
    """
    Tool responsible for validating the configurations
    and parsing them into FreeIPAEntity representations.
    :attr schema: validation schema
    """
    def __init__(self, schema):
        super(ConfigParser, self).__init__()
        self.schema = voluptuous.Schema(schema)


class UserConfigParser(ConfigParser):
    """
    User entity validator & parser.
    """
    def __init__(self):
        super(UserConfigParser, self).__init__(schema_users)

    def parse(self, data):
        """
        Validate user configuration and return parsed FreeIPAUser list.
        :param dict data: dictionary of parsed user entities to validate
        """
        users = []
        for key, value in data.iteritems():
            try:
                users.extend(
                    FreeIPAUser(login, entry)
                    for login, entry in self.schema({key: value}).items())
            except voluptuous.Error as e:
                raise ConfigError(e)
        return users

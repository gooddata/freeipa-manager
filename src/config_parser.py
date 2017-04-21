"""
GoodData FreeIPA tooling
Configuration parsing tool

Tools for validating & parsing the FreeIPA
configuration for hosts, users & groups.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import voluptuous

import entities
import schemas
from core import FreeIPAManagerCore
from errors import ConfigError


class ConfigParser(FreeIPAManagerCore):
    """
    Tool responsible for validating the configurations
    and parsing them into FreeIPAEntity representations.
    """
    def __init__(self, schema, entity_class):
        """
        :param dict schema: voluptuous.Schema template to validate configs by
        :param FreeIPAEntity entity_class: entity class to generate from schema
        """
        super(ConfigParser, self).__init__()
        self.schema = voluptuous.Schema(schema)
        self.entity_class = entity_class

    def parse(self, data):
        """
        Validate the given configuration and parse entity objects.
        :param dict data: dictionary of entity configurations to validate
        """
        entities = []
        for key, value in data.iteritems():
            try:
                entities.extend(
                    self.entity_class(name, entry)
                    for name, entry in self.schema({key: value}).items())
            except voluptuous.Error as e:
                raise ConfigError(e)
        return entities


class UserConfigParser(ConfigParser):
    """
    User entity validator & parser.
    """
    def __init__(self):
        super(UserConfigParser, self).__init__(
            schemas.schema_users, entities.FreeIPAUser)


class UserGroupConfigParser(ConfigParser):
    """
    User group entity validator & parser.
    """
    def __init__(self):
        super(UserGroupConfigParser, self).__init__(
            schemas.schema_usergroups, entities.FreeIPAUserGroup)

"""
GoodData FreeIPA tooling
Configuration parsing tool

Tools for validating & parsing the FreeIPA
configuration for hosts, users & groups.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import voluptuous
from abc import ABCMeta, abstractproperty

import entities
import schemas
import utils
from core import FreeIPAManagerCore
from errors import ConfigError


class ConfigParser(FreeIPAManagerCore):
    """
    Abstract class serving as a base for entity type-specific parsers.
    """
    __metaclass__ = ABCMeta

    def parse(self, data):
        """
        Validate the given configuration and parse entity objects.
        :param dict data: dictionary of entity configurations to validate
        """
        entities = []
        for key, value in data.iteritems():
            try:
                entities.extend(
                    self.entity_class(name, self.convert(entry))
                    for name, entry in self.schema({key: value}).items())
            except voluptuous.Error as e:
                raise ConfigError(e)
        return entities

    @abstractproperty
    def schema(self):
        """
        :returns: entity parsing schema
        :rtype: voluptuous.Schema
        """
        pass

    @abstractproperty
    def entity_class(self):
        """
        :returns: entity class to be created from parsed configuration
        :rtype: entities.FreeIPAEntity subclass
        """
        pass

    def convert(self, data):
        """
        Convert entry from config format to LDAP format.
        :param dict data: entity data parsed from configuration
        :returns: data transformed to LDAP entry-compatible format
        :rtype: dict
        """
        result = dict()
        for key, value in data.items():
            new_key = (
                self.key_mapping.get(key) if key in self.key_mapping else key)
            if new_key == 'memberOf':
                result[new_key] = self._map_memberof(value)
            elif new_key == 'manager':
                result[new_key] = [utils.ldap_get_dn('users', value)]
            else:
                result[new_key] = [value]
        return result

    def _map_memberof(self, memberOf):
        """
        Parse memberOf entry of configuration into an LDAP-compatible list.
        :param dict memberOf: memberOf dictionary parsed from config file
        :returns: list of LDAP DN values
        :rtype: list
        """
        result = list()
        for conftype in memberOf:
            result.extend(
                utils.ldap_get_dn(conftype, i) for i in memberOf[conftype])
        return result


class GroupConfigParser(ConfigParser):
    """Abstract class serving as a base for group-type entity parsers."""
    schema = voluptuous.Schema(schemas.schema_groups)
    key_mapping = {}  # all group config key names are identical to LDAP


class HostGroupConfigParser(GroupConfigParser):
    """Host group entity validator & parser."""
    entity_class = entities.FreeIPAHostGroup


class UserGroupConfigParser(GroupConfigParser):
    """User group entity validator & parser."""
    entity_class = entities.FreeIPAUserGroup


class UserConfigParser(ConfigParser):
    """User entity validator & parser."""
    schema = voluptuous.Schema(schemas.schema_users)
    entity_class = entities.FreeIPAUser
    key_mapping = {
        'emailAddress': 'mail',
        'firstName': 'givenName',
        'lastName': 'sn',
        'organizationUnit': 'ou',
        'githubLogin': 'carLicense',
    }

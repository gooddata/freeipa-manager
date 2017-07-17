"""
GoodData FreeIPA tooling
Configuration parsing tool

Object representations of the entities configured in FreeIPA.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import voluptuous
from abc import ABCMeta, abstractproperty

import schemas
from core import FreeIPAManagerCore
from errors import ConfigError


class FreeIPAEntity(FreeIPAManagerCore):
    """
    General FreeIPA entity (user, group etc.) representation.
    Can only be used via subclasses, not directly.
    """
    __metaclass__ = ABCMeta
    entity_id_type = 'cn'  # entity name identificator inside LDAP DN
    key_mapping = {}  # attribute name mapping between local config and LDAP

    def __init__(self, name, data):
        """
        :param str name: entity name (user login, group name etc.)
        :param dict data: dictionary of entity configuration values
        """
        super(FreeIPAEntity, self).__init__()
        try:
            self.validation_schema(data)
        except voluptuous.Error as e:
            raise ConfigError('Error validating %s: %s' % (name, e))
        self.name = name
        self.data = self._convert(data)

    def _convert(self, data):
        """
        Convert entry from config format to LDAP format. This is needed
        because LDAP configuration storing has some specifics which would
        not be practical to copy in the local configuration (non-intuitive
        attribute names, each attribute as a list and so on).
        :param dict data: entity data parsed from configuration
        :returns: data transformed to LDAP entry-compatible format
        :rtype: dict
        """
        result = dict()
        for key, value in data.items():
            new_key = self.key_mapping.get(key, key.lower())
            if new_key == 'memberof':
                result[new_key] = self._map_memberof(value)
            else:
                if isinstance(value, list):
                    result[new_key] = tuple(value)
                elif new_key in ('memberhost', 'memberuser'):
                    result[new_key] = value
                else:
                    result[new_key] = (value,)
        return result

    def _map_memberof(self, membership_data):
        """
        Parse memberOf entry of entity configuration to a list
        of (entity type, name) tuples for better parsing.
        :param dict membership_data: memberOf dictionary parsed from config
        :returns: list of (entity type, name) tuple values
        :rtype: list
        """
        result = list()
        for entity_type in membership_data:
            try:
                entity_class = self.get_entity_class(entity_type)
            except KeyError:
                raise ConfigError(
                    '%s cannot be a member of non-existent class type "%s"' %
                    (self.name, entity_type))
            for target in membership_data[entity_type] or []:
                result.append((entity_class.entity_name, target))
        return result

    @staticmethod
    def get_entity_class(name):
        for entity_class in [
                FreeIPAHBACRule, FreeIPAHostGroup, FreeIPASudoRule,
                FreeIPAUserGroup, FreeIPAUser]:
            if (
                    entity_class.entity_name == name or
                    entity_class.entity_name_pl == name):
                return entity_class
        raise KeyError(name)

    @abstractproperty
    def validation_schema(self):
        """
        :returns: entity validation schema
        :rtype: voluptuous.Schema
        """

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        return type(self) is type(other) and self.name == other.name

    def __ne__(self, other):
        return not self == other


class FreeIPAGroup(FreeIPAEntity):
    """Abstract representation a FreeIPA group entity (host/user group)."""
    meta_group_suffix = ''

    @property
    def is_meta(self):
        """
        Check whether the group is a meta-group.
        A meta-group can only contain other groups, not hosts/users.
        If meta_group_suffix is an empty string, this is not enforced.
        """
        return self.meta_suffix and not self.name.endswith(self.meta_suffix)

    @property
    def meta_suffix(self):
        return self.meta_group_suffix


class FreeIPAHostGroup(FreeIPAGroup):
    """Representation of a FreeIPA host group entity."""
    entity_name = 'hostgroup'
    entity_name_pl = 'hostgroups'
    meta_group_suffix = '-hosts'
    validation_schema = voluptuous.Schema(schemas.schema_hostgroups)


class FreeIPAUserGroup(FreeIPAGroup):
    """Representation of a FreeIPA user group entity."""
    entity_name = 'group'
    entity_name_pl = 'groups'
    meta_group_suffix = '-users'
    validation_schema = voluptuous.Schema(schemas.schema_usergroups)


class FreeIPAUser(FreeIPAEntity):
    """Representation of a FreeIPA user entity."""
    entity_name = 'user'
    entity_name_pl = 'users'
    key_mapping = {
        'emailAddress': 'mail',
        'firstName': 'givenname',
        'lastName': 'sn',
        'organizationUnit': 'ou',
        'githubLogin': 'carlicense'
    }
    entity_id_type = 'uid'
    validation_schema = voluptuous.Schema(schemas.schema_users)


class FreeIPARule(FreeIPAEntity):
    """Abstract class covering HBAC and sudo rules."""


class FreeIPAHBACRule(FreeIPARule):
    """Representation of a FreeIPA HBAC (host-based access control) rule."""
    entity_name = 'hbacrule'
    entity_name_pl = 'hbacrules'
    key_mapping = {'enabled': 'ipaenabledflag'}
    validation_schema = voluptuous.Schema(schemas.schema_hbac)


class FreeIPASudoRule(FreeIPARule):
    """Representation of a FreeIPA sudo rule."""
    entity_name = 'sudorule'
    entity_name_pl = 'sudorules'
    key_mapping = {
        'enabled': 'ipaenabledflag',
        'options': 'ipasudoopt',
        'runAsGroupCategory': 'ipasudorunasgroupcategory',
        'runAsUserCategory': 'ipasudorunasusercategory'
    }
    validation_schema = voluptuous.Schema(schemas.schema_sudo)

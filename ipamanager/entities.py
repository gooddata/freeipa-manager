"""
GoodData FreeIPA tooling
Configuration parsing tool

Object representations of the entities configured in FreeIPA.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import voluptuous
from abc import ABCMeta, abstractproperty

import schemas
from command import Command
from core import FreeIPAManagerCore
from errors import ConfigError


class FreeIPAEntity(FreeIPAManagerCore):
    """
    General FreeIPA entity (user, group etc.) representation.
    Can only be used via subclasses, not directly.
    """
    __metaclass__ = ABCMeta
    entity_id_type = 'cn'  # entity name identificator in FreeIPA
    key_mapping = {}  # attribute name mapping between local config and FreeIPA
    ignored = []  # list of ignored entities for each entity type

    def __init__(self, name, data, path=None):
        """
        :param str name: entity name (user login, group name etc.)
        :param dict data: dictionary of entity configuration values
        :param str path: path to file the entity was parsed from
        """
        super(FreeIPAEntity, self).__init__()
        if not data:  # may be None; we want to ensure dictionary
            data = dict()
        self.name = name
        self.path = path
        if self.path:  # created from local config
            try:
                self.validation_schema(data)
            except voluptuous.Error as e:
                raise ConfigError('Error validating %s: %s' % (name, e))
            self.data = self._convert(data)
            self.raw = data
        else:
            self.data = data

    def _convert(self, data):
        """
        Convert entry from config format to LDAP format. This is needed
        because LDAP configuration storing has some specifics which would
        not be practical to copy in the local configuration (non-intuitive
        attribute names, each attribute as a list and so on).
        :param dict data: entity data parsed from configuration
        :returns: data transformed to FreeIPA-compatible format
        :rtype: dict with values of tuples (except for membership attributes,
                which are processed separately without direct upload to API)
        """
        result = dict()
        for key, value in data.iteritems():
            new_key = self.key_mapping.get(key, key)
            if new_key == 'memberOf':
                self._check_memberof(value)
                result[new_key] = value
            elif isinstance(value, list):
                result[new_key] = tuple(value)
            else:
                result[new_key] = (value,)
        return result

    def _check_memberof(self, member_of):
        for entity_type in member_of:
            try:
                self.get_entity_class(entity_type)
            except KeyError:
                raise ConfigError(
                    'Cannot be a member of non-existent entity type %s'
                    % entity_type)

    def create_commands(self, remote_entity=None):
        """
        Create commands to execute in order
        to sync entity with its FreeIPA counterpart.
        :param dict remote_entity: remote entity data
        :returns: list of Command objects to execute
        :rtype: list(Command)
        """
        diff = dict()
        for key in self.managed_attributes:
            local_value = self.data.get(key, ())
            if not remote_entity:
                if local_value:
                    diff[key.lower()] = local_value
            else:
                remote_value = remote_entity.get(key.lower(), ())
                if sorted(local_value) != sorted(remote_value):
                    diff[key.lower()] = local_value
        if diff or not remote_entity:  # create entity even without params
            if remote_entity:  # modify existing entity
                command = '%s_mod' % self.entity_name
            else:  # add new entity
                command = '%s_add' % self.entity_name
            return [Command(command, diff, self.name, self.entity_id_type)]
        return []

    @staticmethod
    def get_entity_class(name):
        for entity_class in [
                FreeIPAHBACRule, FreeIPAHostGroup, FreeIPASudoRule,
                FreeIPAUserGroup, FreeIPAUser]:
            if entity_class.entity_name == name:
                return entity_class
        raise KeyError(name)

    @abstractproperty
    def validation_schema(self):
        """
        :returns: entity validation schema
        :rtype: voluptuous.Schema
        """

    @abstractproperty
    def managed_attributes(self):
        """
        Return a list of properties that are managed for given entity type.
        NOTE: the list should NOT include attributes that are managed via
        separate commands, like memberOf/memberHost/memberUser or ipasudoopt.
        :returns: list of entity's managed attributes
        :rtype: list(str)
        """

    def __repr__(self):
        return '%s %s' % (self.entity_name, self.name)

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return type(self) is type(other) and self.name == other.name

    def __ne__(self, other):
        return not self == other


class FreeIPAGroup(FreeIPAEntity):
    """Abstract representation a FreeIPA group entity (host/user group)."""
    managed_attributes = ['description']
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
    meta_group_suffix = '-hosts'
    validation_schema = voluptuous.Schema(schemas.schema_hostgroups)


class FreeIPAUserGroup(FreeIPAGroup):
    """Representation of a FreeIPA user group entity."""
    entity_name = 'group'
    meta_group_suffix = '-users'
    validation_schema = voluptuous.Schema(schemas.schema_usergroups)


class FreeIPAUser(FreeIPAEntity):
    """Representation of a FreeIPA user entity."""
    entity_name = 'user'
    managed_attributes = ['givenName', 'sn', 'initials', 'mail',
                          'ou', 'manager', 'carLicense', 'title']
    key_mapping = {
        'emailAddress': 'mail',
        'firstName': 'givenName',
        'lastName': 'sn',
        'organizationUnit': 'ou',
        'githubLogin': 'carLicense'
    }
    entity_id_type = 'uid'
    validation_schema = voluptuous.Schema(schemas.schema_users)


class FreeIPARule(FreeIPAEntity):
    """Abstract class covering HBAC and sudo rules."""

    def create_commands(self, remote_entity=None):
        """
        Create commands to execute in order to update the rule.
        Extends the basic command creation
        to account for adding/removing rule members.
        :param dict remote_entity: remote rule data
        :returns: list of commands to execute
        :rtype: list(Command)
        """
        result = super(FreeIPARule, self).create_commands(remote_entity)
        result.extend(self._process_rule_membership(remote_entity))
        return result

    def _process_rule_membership(self, remote_entity):
        """
        Prepare a command for a hbac/sudo rule membership update.
        If the rule previously had any members, these are removed
        as a rule can only have one usergroup and one hostgroup as members.
        :param FreeIPArule remote_entity: remote entity data (may be None)
        """
        commands = []
        for key, member_type, cmd_key in (('memberHost', 'hostgroup', 'host'),
                                          ('memberUser', 'group', 'user')):
            local_members = set(self.data.get(key, []))
            if remote_entity:
                search_key = '%s_%s' % (key.lower(), member_type)
                remote_members = set(remote_entity.get(search_key, []))
            else:
                remote_members = set()
            command = '%s_add_%s' % (self.entity_name, cmd_key)
            for member in local_members - remote_members:
                diff = {member_type: member}
                commands.append(
                    Command(command, diff, self.name, self.entity_id_type))
            command = '%s_remove_%s' % (self.entity_name, cmd_key)
            for member in remote_members - local_members:
                diff = {member_type: member}
                commands.append(
                    Command(command, diff, self.name, self.entity_id_type))
        return commands


class FreeIPAHBACRule(FreeIPARule):
    """Representation of a FreeIPA HBAC (host-based access control) rule."""
    entity_name = 'hbacrule'
    managed_attributes = ['description']
    validation_schema = voluptuous.Schema(schemas.schema_hbac)


class FreeIPASudoRule(FreeIPARule):
    """Representation of a FreeIPA sudo rule."""
    entity_name = 'sudorule'
    managed_attributes = [
        'cmdCategory', 'description',
        'ipaSudoRunAsGroupCategory', 'ipaSudoRunAsUserCategory']
    key_mapping = {
        'options': 'ipaSudoOpt',
        'runAsGroupCategory': 'ipaSudoRunAsGroupCategory',
        'runAsUserCategory': 'ipaSudoRunAsUserCategory'
    }
    validation_schema = voluptuous.Schema(schemas.schema_sudo)

    def create_commands(self, remote_entity=None):
        """
        Create commands to execute in order to update the rule.
        Extends the basic command creation with sudorule option update.
        :param dict remote_entity: remote rule data
        :returns: list of commands to execute
        :rtype: list(Command)
        """
        result = super(FreeIPASudoRule, self).create_commands(remote_entity)
        result.extend(self._parse_sudo_options(remote_entity))
        return result

    def _parse_sudo_options(self, remote_entity):
        """
        Prepare commands for sudo rule options update. This includes
        deletion of old options that are no longer in configuration
        as well as addition of new options.
        :param dict remote_entity: remote entity data (can be None)
        :returns: list of sudorule option update commands to execute
        :rtype: list(Command)
        """
        commands = []
        local_options = set(self.data.get('ipaSudoOpt', []))
        if remote_entity:
            remote_options = set(remote_entity.get('ipasudoopt', []))
        else:
            remote_options = set()
        command = 'sudorule_add_option'
        for opt in local_options - remote_options:
            diff = {'ipasudoopt': [opt]}
            commands.append(
                Command(command, diff, self.name, self.entity_id_type))
        command = 'sudorule_remove_option'
        for opt in remote_options - local_options:
            diff = {'ipasudoopt': [opt]}
            commands.append(
                Command(command, diff, self.name, self.entity_id_type))
        return commands

"""
GoodData FreeIPA tooling
Configuration parsing tool

Object representations of the entities configured in FreeIPA.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import os
import re
import voluptuous
import yaml
from abc import ABCMeta, abstractproperty

import schemas
from command import Command
from core import FreeIPAManagerCore
from errors import ConfigError, ManagerError


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
        :param str path: path to file the entity was parsed from;
                         if None, indicates creation of entity from FreeIPA
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
            self.data_ipa = self._convert_to_ipa(data)
            self.data_repo = data
        else:  # created from FreeIPA
            self.data_ipa = data
            self.data_repo = self._convert_to_repo(data)

    def _convert_to_ipa(self, data):
        """
        Convert entity data to IPA format.
        :param dict data: entity data in repository format
        :returns: dictionary of data in IPA format
        :rtype: dict
        """
        result = dict()
        for key, value in data.iteritems():
            new_key = self.key_mapping.get(key, key).lower()
            if new_key == 'memberof':
                self._check_memberof(value)
                result[new_key] = value
            elif isinstance(value, list):
                result[new_key] = tuple(unicode(i) for i in value)
            else:
                result[new_key] = (unicode(value),)
        return result

    def _convert_to_repo(self, data):
        """
        Convert entity data to repo format.
        :param dict data: entity data in IPA format
        :returns: dictionary of data in repository format
        :rtype: dict
        """
        result = dict()
        for attr in self.managed_attributes_pull:
            if attr.lower() in data:
                key = attr
                if attr in self.key_mapping.itervalues():
                    key = [
                        k for k, v in self.key_mapping.items() if v == attr][0]
                value = data[attr.lower()]
                if isinstance(value, tuple):
                    if len(value) > 1:
                        result[key] = list(value)
                    else:
                        result[key] = value[0]
                else:
                    result[key] = value
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
        :param FreeIPAEntity remote_entity: remote entity
        :returns: list of Command objects to execute
        :rtype: list(Command)
        """
        diff = dict()
        for key in self.managed_attributes_push:
            local_value = self.data_ipa.get(key.lower(), ())
            if not remote_entity:
                if local_value:
                    diff[key.lower()] = local_value
            else:
                remote_value = remote_entity.data_ipa.get(key.lower(), ())
                if sorted(local_value) != sorted(remote_value):
                    diff[key.lower()] = local_value
        if diff or not remote_entity:  # create entity even without params
            if remote_entity:  # modify existing entity
                command = '%s_mod' % self.entity_name
            else:  # add new entity
                command = '%s_add' % self.entity_name
            return [Command(command, diff, self.name, self.entity_id_type)]
        return []

    def update_repo_data(self, additional):
        """
        Update repo-format data with additional attributes.
        Used for adding membership attributes to data.
        :param dict additional: dictionary to update entity data with
        :rtype: None
        """
        self.data_repo.update(additional or {})

    def write_to_file(self):
        if not self.path:
            raise ManagerError(
                '%s has no file path, nowhere to write.' % repr(self))
        try:
            with open(self.path, 'w') as target:
                data = {self.name: self.data_repo or None}
                yaml.dump(data, stream=target, Dumper=EntityDumper,
                          default_flow_style=False, explicit_start=True)
                self.lg.debug('%s written to file', self)
        except (IOError, OSError, yaml.YAMLError) as e:
            raise ConfigError(
                'Cannot write %s to %s: %s' % (repr(self), self.path, e))

    def delete_file(self):
        if not self.path:
            raise ManagerError(
                '%s has no file path, cannot delete.' % repr(self))
        try:
            os.unlink(self.path)
            self.lg.debug('%s config file deleted', self)
        except OSError as e:
            raise ConfigError(
                'Cannot delete %s at %s: %s' % (repr(self), self.path, e))

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
    def managed_attributes_push(self):
        """
        Return a list of properties that are managed for given entity type
        when pushing configuration from local repo to FreeIPA.
        NOTE: the list should NOT include attributes that are managed via
        separate commands, like memberOf/memberHost/memberUser or ipasudoopt.
        :returns: list of entity's managed attributes
        :rtype: list(str)
        """

    @property
    def managed_attributes_pull(self):
        """
        Return a list of properties that are managed for given entity type.
        when pulling configuration from FreeIPA to local repository.
        :returns: list of entity's managed attributes
        :rtype: list(str)
        """
        return self.managed_attributes_push

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
    managed_attributes_push = ['description']

    @abstractproperty
    def allowed_members(self):
        """
        :returns: list of entity types that can be members of this entity
        :rtype: list(FreeIPAEntity)
        """


class FreeIPAHostGroup(FreeIPAGroup):
    """Representation of a FreeIPA host group entity."""
    entity_name = 'hostgroup'
    validation_schema = voluptuous.Schema(schemas.schema_hostgroups)
    allowed_members = ['hostgroup']


class FreeIPAUserGroup(FreeIPAGroup):
    """Representation of a FreeIPA user group entity."""
    entity_name = 'group'
    validation_schema = voluptuous.Schema(schemas.schema_usergroups)
    allowed_members = ['user', 'group']

    def can_contain_users(self, pattern):
        """
        Check whether the group can contain users directly.
        If the pattern is None, no restrictions are applied.
        :param str pattern: regex to check name by (not enforced if empty)
        """
        return not pattern or re.match(pattern, self.name)

    def cannot_contain_users(self, pattern):
        """
        Check whether the group can not contain users directly.
        Used for determining if the group can be a member of a sudo/HBAC rule.
        If the pattern is None, no restrictions are applied.
        :param str pattern: regex to check name by (not enforced if empty)
        """
        return not pattern or not re.match(pattern, self.name)


class FreeIPAUser(FreeIPAEntity):
    """Representation of a FreeIPA user entity."""
    entity_name = 'user'
    managed_attributes_push = ['givenName', 'sn', 'initials', 'mail',
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
        for key, member_type, cmd_key in (('memberhost', 'hostgroup', 'host'),
                                          ('memberuser', 'group', 'user')):
            local_members = set(self.data_ipa.get(key, []))
            if remote_entity:
                search_key = '%s_%s' % (key, member_type)
                remote_members = set(
                    remote_entity.data_ipa.get(search_key, []))
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
    managed_attributes_push = ['description']
    validation_schema = voluptuous.Schema(schemas.schema_hbac)


class FreeIPASudoRule(FreeIPARule):
    """Representation of a FreeIPA sudo rule."""
    entity_name = 'sudorule'
    managed_attributes_push = [
        'cmdCategory', 'description',
        'ipaSudoRunAsGroupCategory', 'ipaSudoRunAsUserCategory']
    managed_attributes_pull = managed_attributes_push + ['ipaSudoOpt']
    key_mapping = {
        'options': 'ipaSudoOpt',
        'runAsGroupCategory': 'ipaSudoRunAsGroupCategory',
        'runAsUserCategory': 'ipaSudoRunAsUserCategory'
    }
    validation_schema = voluptuous.Schema(schemas.schema_sudo)

    def _convert_to_repo(self, data):
        result = super(FreeIPASudoRule, self)._convert_to_repo(data)
        if isinstance(result.get('options'), unicode):
            result['options'] = [result['options']]
        return result

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
        local_options = set(self.data_repo.get('options', []))
        if remote_entity:
            remote_options = set(remote_entity.data_ipa.get('ipasudoopt', []))
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


class EntityDumper(yaml.SafeDumper):
    """YAML dumper subclass used to fix under-indent of lists when dumping."""
    def __init__(self, *args, **kwargs):
        super(EntityDumper, self).__init__(*args, **kwargs)
        self.add_representer(type(None), self._none_representer())

    def increase_indent(self, flow=False, indentless=False):
        return super(EntityDumper, self).increase_indent(flow, False)

    def _none_representer(self):
        """
        Enable correct representation of empty values in config
        by representing None as empty string instead of 'null'.
        """
        def representer(dumper, value):
            return dumper.represent_scalar(u'tag:yaml.org,2002:null', '')
        return representer

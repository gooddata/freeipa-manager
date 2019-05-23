#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.
"""
FreeIPA Manager - entity module

Object representations of the entities configured in FreeIPA.
"""

import os
import re
import voluptuous
import yaml
from abc import ABCMeta, abstractproperty

import schemas
from command import Command
from core import FreeIPAManagerCore
from errors import ConfigError, ManagerError, IntegrityError


class FreeIPAEntity(FreeIPAManagerCore):
    """
    General FreeIPA entity (user, group etc.) representation.
    Can only be used via subclasses, not directly.
    """
    __metaclass__ = ABCMeta
    entity_id_type = 'cn'  # entity name identificator in FreeIPA
    key_mapping = {}  # attribute name mapping between local config and FreeIPA
    ignored = []  # list of ignored entities for each entity type
    allowed_members = []

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
        self.metaparams = data.pop('metaparams', dict())
        if self.path:  # created from local config
            try:
                self.validation_schema(data)
            except voluptuous.Error as e:
                raise ConfigError('Error validating %s: %s' % (name, e))
            if not path.endswith('.yaml'):  # created from template tool
                path, name = os.path.split(self.path)
                self.path = '%s.yaml' % os.path.join(
                    path, name.replace('-', '_'))
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
            elif isinstance(value, bool):
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
                # find reverse (IPA -> repo) attribute name mapping
                for k, v in self.key_mapping.iteritems():
                    if v == attr:
                        key = k
                        break
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

    def normalize(self):
        """
        Re-structure entity's data in such a way that it can be stored
        into the configuration file in a normalized format. This is used
        when round-trip loading and saving a configuration.
        """
        memberof = self.data_repo.pop('memberOf', None)
        if memberof:
            for target_type, target_list in memberof.iteritems():
                memberof[target_type] = sorted(target_list)
            self.data_repo['memberOf'] = memberof

    def write_to_file(self):
        if not self.path:
            raise ManagerError(
                '%s has no file path, nowhere to write.' % repr(self))
        if self.metaparams:
            self.data_repo.update({'metaparams': self.metaparams})
        # don't write default attributes into file
        for key in self.default_attributes:
            self.data_repo.pop(key, None)
        try:
            with open(self.path, 'w') as target:
                data = {self.name: self.data_repo or None}
                yaml.dump(data, stream=target, Dumper=EntityDumper,
                          default_flow_style=False, explicit_start=True)
                self.lg.debug('%s written to file', repr(self))
        except (IOError, OSError, yaml.YAMLError) as e:
            raise ConfigError(
                'Cannot write %s to %s: %s' % (repr(self), self.path, e))

    def delete_file(self):
        if not self.path:
            raise ManagerError(
                '%s has no file path, cannot delete.' % repr(self))
        try:
            os.unlink(self.path)
            self.lg.debug('%s config file deleted', repr(self))
        except OSError as e:
            raise ConfigError(
                'Cannot delete %s at %s: %s' % (repr(self), self.path, e))

    @staticmethod
    def get_entity_class(name):
        for entity_class in [
                FreeIPAHBACRule, FreeIPAHBACService,
                FreeIPAHBACServiceGroup, FreeIPAHostGroup, FreeIPAPermission,
                FreeIPAPrivilege, FreeIPARole, FreeIPAService,
                FreeIPASudoRule, FreeIPAUser, FreeIPAUserGroup]:
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

    @property
    def default_attributes(self):
        """
        Return a list of default attributes for each entity of the given type.
        These attributes will not be written into the YAML file when pulling.
        :returns: list of entity's attributes that have single default value
        :rtype: list(str)
        """
        return []

    def __repr__(self):
        return '%s %s' % (self.entity_name, self.name)

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return type(self) is type(other) and self.name == other.name

    def __ne__(self, other):
        return not (self == other)

    def __gt__(self, other):
        return self.name > other.name

    def __lt__(self, other):
        return self.name < other.name


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
    allowed_members = ['hostgroup']
    validation_schema = voluptuous.Schema(schemas.schema_hostgroups)


class FreeIPAUserGroup(FreeIPAGroup):
    """Representation of a FreeIPA user group entity."""
    entity_name = 'group'
    managed_attributes_pull = ['description', 'posix']
    allowed_members = ['user', 'group']
    validation_schema = voluptuous.Schema(schemas.schema_usergroups)

    def __init__(self, name, data, path=None):
        """
        :param str name: entity name (user login, group name etc.)
        :param dict data: dictionary of entity configuration values
        :param str path: path to file the entity was parsed from;
                         if None, indicates creation of entity from FreeIPA
        """
        if not path:  # entity created from FreeIPA, not from config
            data['posix'] = u'posixgroup' in data.get(u'objectclass', [])
        super(FreeIPAUserGroup, self).__init__(name, data, path)
        self.posix = self.data_repo.get('posix', True)

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

    def _process_posix_setting(self, remote_entity):
        posix_diff = dict()
        description = None
        if remote_entity:
            if self.posix and not remote_entity.posix:
                posix_diff = {u'posix': True}
                description = 'group_mod %s (make POSIX)' % self.name
            elif not self.posix and remote_entity.posix:
                posix_diff = {'setattr': (u'gidnumber=',),
                              'delattr': (u'objectclass=posixgroup',)}
                description = 'group_mod %s (make non-POSIX)' % self.name
        elif not self.posix:  # creation of new non-POSIX group
            posix_diff = {u'nonposix': True}
        return (posix_diff, description)

    def create_commands(self, remote_entity=None):
        """
        Create commands to execute in order to update the rule.
        Extends the basic command creation with POSIX/non-POSIX setting.
        :param dict remote_entity: remote rule data
        :returns: list of commands to execute
        :rtype: list(Command)
        """
        commands = super(FreeIPAUserGroup, self).create_commands(remote_entity)
        posix_diff, description = self._process_posix_setting(remote_entity)
        if posix_diff:
            if not commands:  # no diff but POSIX setting, new command needed
                cmd = Command('group_mod', posix_diff,
                              self.name, self.entity_id_type)
                cmd.description = description
                return [cmd]
            else:  # update POSIX setting as part of existing command
                commands[0].update(posix_diff)
        return commands


class FreeIPAUser(FreeIPAEntity):
    """Representation of a FreeIPA user entity."""
    entity_name = 'user'
    entity_id_type = 'uid'
    managed_attributes_push = ['givenName', 'sn', 'initials', 'mail',
                               'ou', 'manager', 'carLicense', 'title']
    key_mapping = {
        'emailAddress': 'mail',
        'firstName': 'givenName',
        'lastName': 'sn',
        'organizationUnit': 'ou',
        'githubLogin': 'carLicense'
    }
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
        for key, member_type, cmd_key in (
                ('memberhost', 'hostgroup', 'host'),
                ('memberuser', 'group', 'user'),
                ('memberservice', 'hbacsvc', 'service')):
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
    default_attributes = ['serviceCategory']
    managed_attributes_push = ['description', 'serviceCategory']
    validation_schema = voluptuous.Schema(schemas.schema_hbac)

    def __init__(self, name, data, path=None):
        """
        Create a HBAC rule instance.
        This override is needed to set the servicecat parameter.
        """
        if path:  # only edit local entities
            if not data:  # may be None; we want to ensure dictionary
                data = dict()
            if 'memberService' not in data:
                data.update({'serviceCategory': 'all'})
            elif 'serviceCategory' in data:
                raise IntegrityError(
                    '%s cannot contain both memberService and serviceCategory'
                    % name)
        super(FreeIPAHBACRule, self).__init__(name, data, path)


class FreeIPASudoRule(FreeIPARule):
    """Representation of a FreeIPA sudo rule."""
    entity_name = 'sudorule'
    default_attributes = [
        'cmdCategory', 'options', 'runAsGroupCategory', 'runAsUserCategory']
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

    def __init__(self, name, data, path=None):
        """
        Create a sudorule instance.
        This override is needed to set the options & runAs params.
        """
        if path:  # only edit local entities
            if not data:  # may be None; we want to ensure dictionary
                data = dict()
            data.update({'options': ['!authenticate', '!requiretty'],
                         'cmdCategory': 'all',
                         'runAsUserCategory': 'all',
                         'runAsGroupCategory': 'all'})
        super(FreeIPASudoRule, self).__init__(name, data, path)

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


class FreeIPAHBACService(FreeIPAEntity):
    """Entity to hold the info about FreeIPA HBACServices"""
    entity_name = 'hbacsvc'
    managed_attributes_push = ['description']
    managed_attributes_pull = managed_attributes_push
    validation_schema = voluptuous.Schema(schemas.schema_hbacservices)


class FreeIPAHBACServiceGroup(FreeIPAEntity):
    """Entity to hold the info about FreeIPA HBACServiceGroups"""
    entity_name = 'hbacsvcgroup'
    managed_attributes_push = ['description']
    managed_attributes_pull = managed_attributes_push
    allowed_members = ['hbacsvc']
    validation_schema = voluptuous.Schema(schemas.schema_hbacsvcgroups)


class FreeIPARole(FreeIPAEntity):
    """Entity to hold the info about FreeIPA Roles"""
    entity_name = 'role'
    managed_attributes_pull = ['description']
    managed_attributes_push = managed_attributes_pull
    allowed_members = ['user', 'group', 'service', 'hostgroup']
    validation_schema = voluptuous.Schema(schemas.schema_roles)


class FreeIPAPrivilege(FreeIPAEntity):
    """Entity to hold the info about FreeIPA Privilege"""
    entity_name = 'privilege'
    managed_attributes_pull = ['description']
    managed_attributes_push = managed_attributes_pull
    allowed_members = ['role']
    validation_schema = voluptuous.Schema(schemas.schema_privileges)


class FreeIPAPermission(FreeIPAEntity):
    """Entity to hold the info about FreeIPA Permission"""
    entity_name = 'permission'
    managed_attributes_pull = ['description', 'subtree', 'attrs',
                               'ipapermlocation', 'ipapermright',
                               'ipapermdefaultattr']
    managed_attributes_push = managed_attributes_pull
    key_mapping = {
        'grantedRights': 'ipapermright',
        'attributes': 'attrs',
        'location': 'ipapermlocation',
        'defaultAttr': 'ipapermdefaultattr'
    }
    allowed_members = ['privilege']
    validation_schema = voluptuous.Schema(schemas.schema_permissions)


class FreeIPAService(FreeIPAEntity):
    """
    Entity to hold the info about FreeIPA Services
    PUSH NOT SUPPORTED yet
    """
    entity_name = 'service'
    entity_id_type = 'krbcanonicalname'
    managed_attributes_push = []  # Empty because we don't support push
    managed_attributes_pull = ['managedby_host', 'description']
    key_mapping = {
        'managedBy': 'managedby_host',
    }
    validation_schema = voluptuous.Schema(schemas.schema_services)

    def write_to_file(self):
        """
        Converts the file name format from xyz/hostname.int.na.intgdc.com
        to xyz-hostname_int_na_intgdc_com.yaml
        """
        path, file_name = os.path.split(self.path)
        service_name, _ = file_name.split('@')
        self.path = ('%s-%s.yaml' % (path, service_name.replace('.', '_')))
        super(FreeIPAService, self).write_to_file()


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

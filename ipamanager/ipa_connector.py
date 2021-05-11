#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2021, GoodData Corporation. All rights reserved.
"""
FreeIPA Manager - IPA updating module

Tool for updating a FreeIPA server via API
from local entity configuration.
"""

import re
import os
from ipalib import api

import entities
from command import Command
from core import FreeIPAManagerCore
from entities import FreeIPAEntity
from errors import CommandError, ConfigError, ManagerError
from utils import ENTITY_CLASSES, check_ignored


class IpaConnector(FreeIPAManagerCore):
    """
    Responsible for updating FreeIPA server with changed configuration.
    """
    def __init__(self, parsed, settings):
        super(IpaConnector, self).__init__()
        self.ignored = settings.get('ignore', dict())
        self.repo_entities = parsed
        self.ipa_entities = dict()

    def load_ipa_entities(self):
        """
        Load entities defined on the FreeIPA via API.
        Entity data is saved in `self.ipa_entities` nested dictionary
        with top-level keys being entity types (e.g., 'hostgroup')
        and bottom-level keys being entity names (e.g., 'group-one').
        :raises ManagerError: if there is an error communicating with the API
        :returns: None (entities saved in the `self.ipa_entities` dict)
        """
        self.lg.info('Loading entities from FreeIPA API')
        for entity_class in ENTITY_CLASSES:
            entity_type = entity_class.entity_name
            self.ipa_entities[entity_type] = dict()
            command = '%s_find' % entity_type
            self.lg.debug('Running API command %s', command)
            try:
                parsed = api.Command[command](all=True, sizelimit=0)
            except KeyError:
                raise ManagerError('Undefined API command %s' % command)
            except Exception as e:
                raise ManagerError('Error loading %s entities from API: %s'
                                   % (entity_type, e))
            for data in parsed['result']:
                name = data[entity_class.entity_id_type][0]
                if check_ignored(entity_class, name, self.ignored):
                    self.lg.debug(
                        'Not parsing ignored %s %s', entity_type, name)
                    continue
                self.ipa_entities[entity_type][name] = entity_class(name, data)
            self.lg.info('Parsed %d %ss', len(self.ipa_entities[entity_type]),
                         entity_type)
            self.lg.debug('%ss parsed: %s', entity_type,
                          sorted(self.ipa_entities[entity_type].keys()))
        self.ipa_entity_count = sum(
            len(i) for i in self.ipa_entities.itervalues())
        self.lg.info(
            'Parsed %d entities from FreeIPA API', self.ipa_entity_count)


class IpaUploader(IpaConnector):
    def __init__(self, settings, parsed, threshold, force=False,
                 enable_deletion=False, okta_users=False, okta_groups=[]):
        """
        Initialize an IPA connector object.
        :param dict settings: parsed contents of the settings file
        :param dict parsed: dictionary of entities from `IntegrityChecker`
        :param int threshold: max percentage of entities to edit (1-100)
        :param bool force: execute changes (dry run if False)
        :param bool enable_deletion: enable deleting entities
        :param bool okta_users: push users from Okta instead of Git
        :param [str] okta_groups: list of Okta groups to use for diff
        """
        super(IpaUploader, self).__init__(parsed, settings)
        self.threshold = threshold
        self.force = force
        self.enable_deletion = enable_deletion
        # deletion patterns used to filter commands in add-only mode
        self.deletion_patterns = settings.get(
            'deletion-patterns',
            ['.+_del$', '.+_remove_member$', '.+_remove_option$'])

        # parse Okta-related settings
        okta_settings = settings.get('okta', dict())
        self.okta_users = okta_users
        self.okta_groups = okta_groups
        if self.okta_users:
            self.ignored['user'] = okta_settings.get('ignore', [])

    def _prepare_push(self):
        """
        Prepare the queue of commands to execute as part of FreeIPA update.
        The commands include addition/modification/deletion of entities,
        adding/removing group/rule members and sudorule options. Deletion
        commands are only enqueued when `enable_deletion` attribute is True.
        """
        self.lg.debug('Preparing IPA update commands')
        self.commands = []
        for entity_type in self.repo_entities:
            self.lg.debug('Processing %s entities', entity_type)
            if entity_type == 'service':
                if self.repo_entities[entity_type]:
                    self.lg.warning('Service push not supported yet, skipping')
                    continue
            for entity in self.repo_entities[entity_type].itervalues():
                self.lg.debug('Processing entity %s', entity)
                self._parse_entity_diff(entity)
        self._prepare_del_commands()
        self._filter_deletion_commands()
        self.lg.info('%d commands to execute', len(self.commands))

    def _filter_deletion_commands(self):
        """
        Filter commands to execute in case deletion mode is not enabled.
        """
        if self.enable_deletion:  # all commands should be executed
            return
        filtered_commands = []
        for command in self.commands:
            cmd = command.command
            if any(re.match(regex, cmd) for regex in self.deletion_patterns):
                continue
            filtered_commands.append(command)
        self.commands = filtered_commands

    def _parse_entity_diff(self, entity):
        """
        Prepare update commands for a single entity. This includes creating
        the entity if it doesn't exist or modifying its attributes if it exists
        already. Some attributes require special handling (e.g., group/rule
        membership, which needs to call a command on the group/rule entity, or
        sudorule option add/delete) that is special-cased by auxiliary methods.
        :param FreeIPAEntity entity: local entity instance to process
        """
        remote_entity = self.ipa_entities[entity.entity_name].get(entity.name)
        if not isinstance(entity, entities.FreeIPARule):
            self._process_membership(entity)
        commands = entity.create_commands(remote_entity)
        if commands:
            self.commands.extend(commands)

    def _process_membership(self, entity):
        """
        Prepare membership update commands for an entity. This has 2 phases:
        1. ensure addition to entities listed in entity's memberOf attribute
        2. iterate over all remote entities, ensure deletion from entities that
           have been deleted from the memberOf attribute
        :param FreeIPAEntity entity: entity to process
        """
        self.lg.debug('Processing membership for %s', entity)
        member_of = entity.data_repo.get('memberOf', dict())
        key = 'member_%s' % entity.entity_name
        for target_type in member_of:
            for target_name in member_of[target_type]:
                repo_group = self.repo_entities[target_type][target_name]
                ipa_group = self.ipa_entities[target_type].get(target_name)
                if ipa_group and entity.name in ipa_group.data_ipa.get(
                        key, []):
                    self.lg.debug(
                        '%s already member of %s', entity, repo_group)
                    continue
                command = '%s_add_member' % repo_group.entity_name
                self.commands.append(
                    Command(command, {entity.entity_name: (entity.name,)},
                            repo_group.name, repo_group.entity_id_type))

        target_types = [cls.entity_name for cls in ENTITY_CLASSES
                        if entity.entity_name in cls.allowed_members]
        for target_type in target_types:
            for target in self.ipa_entities[target_type]:
                members = self.ipa_entities[target_type][target].data_ipa.get(
                    'member_%s' % entity.entity_name, [])
                if entity.name in members:
                    if target not in member_of.get(target_type, []):
                        command = '%s_remove_member' % target_type
                        diff = {entity.entity_name: (entity.name,)}
                        self.commands.append(
                            Command(command, diff, target, 'cn'))

    def _prepare_del_commands(self):
        """
        Prepare commands handling entity deletion (.+_del).
        These entities may then be filtered out based on the setting
        of `deletion_patterns` attribute & the value of `enable_deletion` flag.
        """
        for entity_type in self.ipa_entities:
            entity_class = FreeIPAEntity.get_entity_class(entity_type)
            self.lg.debug('Preparing deletion of %s entities', entity_type)
            for name, entity in self.ipa_entities[entity_type].iteritems():
                if name not in self.repo_entities.get(entity_type, dict()):
                    self.lg.debug('Marking %s for deletion', name)
                    command = '%s_del' % entity_type
                    self.commands.append(
                        Command(
                            command, {}, name, entity_class.entity_id_type))

    def push(self):
        """
        Execute update by running commands from the execution queue
        prepared by the `prepare_update` method.
        Commands will only be executed if their total number does not
        exceed the `threshold` attribute.
        :raises ManagerError: in case of exceeded threshold/API error
        """
        self.load_ipa_entities()
        self._prepare_push()
        if not self.commands:
            self.lg.info('FreeIPA consistent with local config, nothing to do')
            return
        if not self.force:  # dry run
            self.lg.info('Would execute commands:')
            for command in sorted(self.commands):
                self.lg.info('- %s', command)
        self._check_threshold()

        if self.force:
            # command sorting really important here for correct update!
            for command in sorted(self.commands):
                try:
                    command.execute(api)
                except CommandError as e:
                    err = 'Error executing %s: %s' % (command.description, e)
                    self.lg.error(err)
                    # only added here to count the number of errors
                    self.errs.append(err)

            if self.errs:
                raise ManagerError(
                    'There were %d errors executing update' % len(self.errs))

    def _check_threshold(self):
        try:
            abs_ratio = float(len(self.commands)) / self.ipa_entity_count
        except ZeroDivisionError:
            abs_ratio = 1
        # cap change ratio to 100 % to avoid threshold issues
        ratio = min(abs_ratio * 100, 100)
        self.lg.debug('%d commands, %d remote entities (%.2f %%)',
                      len(self.commands), self.ipa_entity_count, ratio)
        if ratio > self.threshold:
            raise ManagerError(
                'Threshold exceeded (%.2f %% > %.f %%), aborting'
                % (ratio, self.threshold))
        self.lg.debug('Threshold check passed')


class IpaDownloader(IpaConnector):
    def __init__(self, settings, parsed, repo_path,
                 dry_run=False, add_only=False, pull_types=['user']):
        """
        Initialize an IPA connector object.
        :param dict settings: parsed contents of the settings file
        :param dict parsed: dictionary of entities from `IntegrityChecker`
        :param str repo_path: path to configuration repository
        :param bool force: execute changes (dry run if False)
        :param bool enable_deletion: enable deleting entities
        """
        super(IpaDownloader, self).__init__(parsed, settings)
        self.basepath = repo_path
        self.dry_run = dry_run
        self.add_only = add_only
        self.pull_types = pull_types

    def _prepare_pull(self):
        """
        Prepare pull of all entities before actually running it so that
        we can ensure that selected entities can be written and the pull
        will not fail after writing only a part of entities.
        """
        self.to_write = []
        self.to_delete = []
        for type_to_pull in self.pull_types:
            self.lg.debug('Processing %s entities', type_to_pull)
            for ipa_entity in self.ipa_entities[type_to_pull].itervalues():
                self._update_entity_membership(ipa_entity)
                repo_entity = self.repo_entities[type_to_pull].get(
                    ipa_entity.name)
                if repo_entity:  # update of entity
                    if repo_entity.data_repo != ipa_entity.data_repo:
                        ipa_entity.path = repo_entity.path
                        ipa_entity.metaparams = repo_entity.metaparams
                        if self.dry_run:
                            self.lg.info('Would update %s', repr(ipa_entity))
                        else:
                            self.to_write.append(ipa_entity)
                else:  # new entity creation
                    self._generate_filename(ipa_entity)
                    if self.dry_run:
                        self.lg.info('Would create %s', repr(ipa_entity))
                    else:
                        self.to_write.append(ipa_entity)
            if not self.add_only:
                for name in self.repo_entities[type_to_pull]:
                    repo_entity = self.repo_entities[type_to_pull][name]
                    if name not in self.ipa_entities[type_to_pull]:
                        if self.dry_run:
                            self.lg.info('Would delete %s', repr(repo_entity))
                        else:
                            self.to_delete.append(repo_entity)

    def pull(self):
        """
        Pull configuration from FreeIPA server
        and update local configuration files to match it.
        """
        self.load_ipa_entities()
        self._prepare_pull()
        if self.dry_run:
            return
        self.lg.info('Starting entity writing')
        for entity in self.to_write:
            entity.write_to_file()
        if not self.add_only:
            for entity in self.to_delete:
                entity.delete_file()
        self.lg.info('Entity pulling finished.')

    def _update_entity_membership(self, entity):
        entity.update_repo_data(self._dump_membership(entity))

    def _dump_membership(self, entity):
        result = dict()
        if isinstance(entity, entities.FreeIPARule):
            for config_key, member_type in (
                    ('memberHost', 'hostgroup'),
                    ('memberService', 'hbacsvc'),
                    ('memberUser', 'group')):
                key = '%s_%s' % (config_key.lower(), member_type)
                # filter ignored members
                members = sorted(
                    set(entity.data_ipa.get(key, [])) - set(
                        self.ignored.get(member_type, key)))
                if members:
                    result[config_key] = members
            if result:
                return result
            return None
        for cls in ENTITY_CLASSES:
            if entity.entity_name in cls.allowed_members:
                members = []
                key = 'member_%s' % entity.entity_name
                for ipa_entity in self.ipa_entities[
                        cls.entity_name].itervalues():
                    if entity.name in ipa_entity.data_ipa.get(key, []):
                        members.append(ipa_entity.name)
                if members:
                    result[cls.entity_name] = sorted(members)
        if any(result.itervalues()):
            return {'memberOf': result}
        return None

    def _generate_filename(self, entity):
        if entity.path:
            raise ConfigError(
                '%s already has filepath (%s)' % (entity, entity.path))
        used_names = [
            os.path.relpath(i.path, self.basepath) for i
            in self.repo_entities[entity.entity_name].itervalues()]
        clean_name = entity.name
        for char in ['.', '-', ' ']:
            clean_name = clean_name.replace(char, '_')
        fname = '%ss/%s.yaml' % (entity.entity_name, clean_name)
        if fname in used_names:
            raise ConfigError('%s filename already used' % fname)
        self.lg.debug('Setting %s file path to %s', entity, fname)
        entity.path = os.path.join(self.basepath, fname)

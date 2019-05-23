#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.
"""
FreeIPA Manager - integrity checking module

Tools for checking integrity of entity configurations.
"""

import entities
from core import FreeIPAManagerCore
from errors import IntegrityError
from utils import find_entity


class IntegrityChecker(FreeIPAManagerCore):
    def __init__(self, parsed, settings):
        """
        Create an integrity checker instance.
        :param dict parsed: entities parsed by `ConfigLoader` to check
        :param dict settings: parsed settings file
        """
        super(IntegrityChecker, self).__init__()
        self.entity_dict = parsed
        self.user_group_regex = settings.get('user-group-pattern')
        self.nesting_limit = settings.get('nesting-limit')
        self.nesting = {'group': dict(), 'hostgroup': dict()}

    def check(self):
        """
        Run an integrity check over the whole parsed configuration dictionary.
        :raises IntegrityError: if there is a problem with config integrity
        :returns: None (everything correct if no error is raised)
        """
        if not self.entity_dict:
            self.lg.warning('No entities to check for integrity')
            return
        self.lg.info('Running integrity check')
        self.errs = dict()  # key: (entity type, name), value: error list

        for entity_type in sorted(self.entity_dict):
            self.lg.debug('Checking %s entities', entity_type)
            for entity in self.entity_dict[entity_type].itervalues():
                self._check_single(entity)
        if self.errs:
            raise IntegrityError(
                'There were %d integrity errors in %d entities' %
                (sum(len(i) for i in self.errs.itervalues()), len(self.errs)))
        self.lg.info('Integrity check passed')

    def _check_single(self, entity):
        """
        Check integrity of a single entity. It is verified that it is only
        a member of existing entities (and not of itself), that membership
        adheres to rules defined in the rules file (if any), and that
        there is no cyclic membership (if the entity is a group).
        :param FreeIPAEntity entity: entity to check
        :returns: None (any errors are written to the `self.errs` dictionary)
        """
        self.lg.debug('Checking entity %s', entity)
        if isinstance(entity, entities.FreeIPARule):
            errs = self._check_single_rule_entity(entity)
        else:
            errs = self._check_single_member_entity(entity)
        if errs:
            self.lg.error(
                '%s %s: %s', entity.entity_name, entity.name, '; '.join(errs))
            self.errs[(entity.entity_name, entity.name)] = errs

    def _check_single_rule_entity(self, entity):
        """
        Run checks specific for rule-type entities (HBAC & sudo rules).
        This special case is necessary as membership representation
        is different for rules (they have memberHost and memberUser attributes
        to represent their members while other entities have memberOf attribute
        that reflects their own membership in other entities).
        :param FreeIPARule entity: rule entity to check
        """
        errs = []
        for key, member_type, must_exist in [
                ('memberHost', 'hostgroup', True),
                ('memberService', 'hbacsvc', False),
                ('memberUser', 'group', True)]:
            member_names = entity.data_repo.get(key, [])
            if must_exist and not member_names:
                errs.append('no %s' % key)
                continue
            for name in member_names:
                member = self._find_entity(member_type, name)
                if not member:
                    errs.append('non-existent %s %s' % (key, name))
                    continue
                # check that group does not contain users directly
                if isinstance(member, entities.FreeIPAUserGroup):
                    if not member.cannot_contain_users(self.user_group_regex):
                        errs.append('%s can contain users' % name)
        return errs

    def _check_single_member_entity(self, entity):
        """
        Run checks specific for entities that can be members
        of other entities (i.e. all entities except rules).
        :param FreeIPAEntity entity: entity to check
        """
        errs = []
        member_of = entity.data_repo.get('memberOf', dict())
        if isinstance(entity, entities.FreeIPAUser):
            # check if person's manager exists
            manager = entity.data_repo.get('manager')
            if manager and not self._find_entity('user', manager):
                errs.append('manager %s does not exist' % manager)
        for target_type, targets in member_of.iteritems():
            for target_name in targets:
                target = self._find_entity(target_type, target_name)
                if not target:
                    errs.append('memberOf non-existent %s %s'
                                % (target_type, target_name))
                    continue
                if target == entity:
                    errs.append('memberOf itself')
                    continue
                try:
                    self._check_member_type(entity, target)
                except IntegrityError as e:
                    errs.append(str(e))
                    continue
                if isinstance(entity, entities.FreeIPAUser) and isinstance(
                        target, entities.FreeIPAUserGroup):
                    if not target.can_contain_users(self.user_group_regex):
                        errs.append('%s cannot contain users directly'
                                    % target_name)
        # check for cyclic membership
        if not errs:
            cyclic_path = self._check_cycles(entity)
            if cyclic_path:
                errs.append('Cyclic membership: %s' % (cyclic_path))

        if errs:
            return errs

        # check for nesting limit exceedance
        if isinstance(entity, entities.FreeIPAGroup) and self.nesting_limit:
            nesting = self._check_nesting_level(
                entity.entity_name, entity.name)
            if nesting > self.nesting_limit:
                errs.append('Nesting level exceeded: %d > %d'
                            % (nesting, self.nesting_limit))
        return errs

    def _check_member_type(self, member, target):
        """
        Check that the membership between given entities adheres
        to type constraints of the FreeIPA memberOf relationship.
        :param FreeIPAEntity member: member entity
        :param FreeIPAEntity target: membership target entity
        """
        can_contain_members = (
            entities.FreeIPAGroup, entities.FreeIPARole,
            entities.FreeIPAPrivilege, entities.FreeIPAPermission,
            entities.FreeIPAHBACServiceGroup)
        if not isinstance(target, can_contain_members):
            raise IntegrityError('%s not one of %s, cannot have members'
                                 % (target, can_contain_members))
        if member.entity_name not in target.allowed_members:
            raise IntegrityError('%s can only have members of type %s'
                                 % (target, target.allowed_members))

    def _check_cycles(self, entity):
        """
        Check if there is a membership cycle in the config starting at entity.
        Only called on groups as no other entities can have cyclic membership.
        :param FreeIPAGroup entity: entity (group) to begin checking at
        :returns: cyclic membership entity list if found, else None
        """
        self.lg.debug(
            'Running cycles check for %s %s', entity.entity_name, entity.name)
        stack = [(entity, [])]
        visited = set()
        while stack:
            current, path = stack.pop()
            visited.add(current)
            path.append(current)
            member_of = current.data_repo.get('memberOf', dict())
            for item in member_of.get(current.entity_name, []):
                target = self._find_entity(current.entity_name, item)
                if not target:  # non-existent entity
                    continue
                if target == entity:  # cycle found
                    return path
                if target not in visited:
                    stack.append((target, path))

    def _check_nesting_level(self, entity_type, name):
        """
        Check the level of entity's membership nesting.
        Only checked if the nesting-level value is defined in the settings.
        The `nesting` attribute is used for storing intermediate results
        during recursive evaluation of depth of groups so that no single group
        needs to be calculated more than once. This method does not take care
        of membership cycles since it's only called after the cycles check.
        :param str entity_type: entity type name (group/hostgroup)
        :param str name: entity name
        :returns: maximum depth of nesting
        """
        self.lg.debug('Checking nesting level for %s %s', entity_type, name)
        result = self.nesting.get(entity_type, {}).get(name)
        if result:  # calculated as part of other entity's evaluation
            self.lg.debug('Returning cached nesting level for %s %s (%d)',
                          entity_type, name, result)
            return result
        entity = self._find_entity(entity_type, name)
        # memberOf format is a dict of lists; find the right values safely
        memberof = entity.data_repo.get('memberOf', dict())
        targets = memberof.get(entity_type, [])
        if not targets:
            result = 0
        else:
            result = max(self._check_nesting_level(entity_type, target)
                         for target in targets) + 1
        self.nesting[entity_type][name] = result
        self.lg.debug('Nesting level of %s %s is %d',
                      entity_type, name, result)
        return result

    def _find_entity(self, entity_type, name):
        return find_entity(self.entity_dict, entity_type, name)

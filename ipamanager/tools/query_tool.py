#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.
"""
FreeIPA Manager - query tool

A tool for querying entities for various purposes, like:
- checking if user is a member of a (nested) group,
- security label checking,
- etc.
"""

import argparse
import collections
import logging
import os

from ipamanager.config_loader import ConfigLoader
from ipamanager.errors import ManagerError
from ipamanager.integrity_checker import IntegrityChecker
from ipamanager.utils import _args_common, find_entity
from ipamanager.utils import load_settings, _type_verbosity
from ipamanager.tools.core import FreeIPAManagerToolCore


class QueryTool(FreeIPAManagerToolCore):
    """
    A query tool for inquiry operations over entities,
    like nested membership or security label checking.
    """
    def __init__(self, config, settings=None, loglevel=logging.INFO):
        """
        Initialize the query tool class instance.
        :param str config: path to a freeipa-manager-config folder
        :param str settings: path to a settings file
        :param int loglevel: logging level to use
        """
        self.config = config
        if not settings:
            settings = os.path.join(config, 'settings_common.yaml')
        self.settings = load_settings(settings)
        super(QueryTool, self).__init__(loglevel)
        self.graph = {}
        self.ancestors = {}
        self.paths = {}

    def load(self):
        """
        Load and verify entity config to perform queries on.
        Uses the ConfigLoader and IntegrityChecker components.
        """
        self.lg.info('Running pre-query config load & checks')
        self.entities = ConfigLoader(self.config, self.settings).load()
        self.checker = IntegrityChecker(self.entities, self.settings)
        self.checker.check()
        self.lg.info('Pre-query config load & checks finished')

    def run(self, args):
        """
        Run a query action based on arguments.
        :param argparse.Namespace args: parsed args
        """
        if args.action == 'member':
            self._query_membership(args.members, args.entities)
        elif args.action == 'labels':
            self._query_labels(args)

    def _resolve_entities(self, entity_list):
        """
        Find entities from config based on their types and names.
        :param [str] entity_list: entities in type:name format
        :returns: list of resolved entities
        :rtype: [FreeIPAEntity]
        :raises ManagerError: if an entity is not defined in config
        """
        result = []
        for entity_type, entity_name in entity_list:
            resolved = find_entity(self.entities, entity_type, entity_name)
            if not resolved:
                raise ManagerError('%s %s not found in config'
                                   % (entity_type, entity_name))
            result.append(resolved)
        return result

    def build_graph(self, member):
        """
        Find all entities of which `member` is a member.
        Utilizes the `graph` attribute for caching in case several
        entities with overlapping membership graphs are evaluated.
        :param FreeIPAEntity member: entity to search from
        :returns: list of entities that `member` is a member of
        :rtype: [FreeIPAEntity]
        """
        result = self.graph.get(member, set())
        if result:
            self.lg.debug('Membership for %s already calculated', member)
            return result
        self.lg.debug('Calculating membership graph for %s', member)
        memberof = member.data_repo.get('memberOf', {})
        for entity_type, entity_list in memberof.iteritems():
            for entity_name in entity_list:
                entity = find_entity(self.entities, entity_type, entity_name)
                result.add(entity)
                if entity in self.ancestors:
                    self.ancestors[entity].append(member)
                else:
                    self.ancestors[entity] = [member]
                result.update(self.build_graph(entity))
        self.lg.debug('Found %d entities for %s', len(result), member)
        self.graph[member] = result
        return result

    def check_membership(self, member, entity):
        """
        Check if `member` is a member of `entity`.
        :param FreeIPAEntity member: member to evaluate
        :param FreeIPAEntity entity: entity to evaluate
        :returns: possible paths from member to entity (empty if not a member)
        :rtype: [[FreeIPAEntity]]
        """
        self.build_graph(member)
        paths = self._construct_path(entity, member)
        if paths:
            self.lg.info(
                '%s IS a member of %s; possible paths: [%s]',
                member, entity, '; '.join(' -> '.join(
                    repr(e) for e in path) for path in paths))
        else:
            self.lg.info('%s IS NOT a member of %s', member, entity)
        return paths

    def _query_membership(self, members, entity_names):
        """
        Check membership of each entity from `members`
        in each entity from `entity_names`.
        :param [str] members: members to evaluate (type:name format)
        :param [str] entity_names: entities to evaluate (type:name format)
        """
        member_entities = self._resolve_entities(members)
        entity_list = self._resolve_entities(entity_names)
        for member in member_entities:
            for entity in entity_list:
                self.check_membership(member, entity)

    def _construct_path(self, entity, member):
        """
        Find all paths leading from `member` to `entity`.
        The paths are constructed backwards, based on the `ancestor`
        mapping constructed in the `build_graph` method.
        :param FreeIPAEntity entity: entity to search from
        :param FreeIPAEntity member: member to search towards
        :returns: list of paths from `member` to `entity` ([] if no path found)
        :rtype: [[FreeIPAEntity]]
        """
        if (member, entity) in self.paths:
            self.lg.debug('Using cached paths for %s -> %s', member, entity)
            return self.paths[(member, entity)]
        paths = []
        queue = collections.deque([[entity]])
        while queue:
            current = queue.popleft()
            preds = self.ancestors.get(current[0], [])
            for pred in preds:
                new_path = [pred] + current
                if pred == member:
                    paths.append(new_path)
                else:
                    queue.append(new_path)
        self.paths[(member, entity)] = paths
        self.lg.debug('Found %d paths %s -> %s', len(paths), member, entity)
        return paths

    def check_user_membership(self, user, group):
        """
        Check if `user` is a member of a `group`.
        This function serves as a wrapper for easy usage from other scripts.
        :param str user: name of the user to check
        :param str group: name of the group to check
        :returns: True if `user` is a member of `group`, False otherwise
        :rtype: bool
        """
        user_entity = find_entity(self.entities, 'user', user)
        if not user_entity:
            raise ManagerError('User %s does not exist in config' % user)
        group_entity = find_entity(self.entities, 'group', group)
        if not group_entity:
            raise ManagerError('Group %s does not exist in config' % group)
        return bool(self.check_membership(user_entity, group_entity))

    def list_groups(self, user):
        """
        Find all groups that `user` is a member of.
        This function serves as a wrapper for easy import into other scripts.
        :param str user: name of the user to check
        :returns: generator of group names that `user` is a member of
        :rtype: generator
        """
        user_entity = find_entity(self.entities, 'user', user)
        if not user_entity:
            raise ManagerError('User %s does not exist in config' % user)
        groups = self.build_graph(user_entity)
        return (i.name for i in groups)

    def _query_labels(self, args):
        """
        Run a labels query based on `args.subaction`.
        """
        subactions = {
            'check': lambda a: self.check_label_necessary(a.label, a.group),
            'missing': lambda a: self.list_user_missing_labels(a.user),
            'necessary': lambda a: self.list_necessary_labels(a.group),
            'user': lambda a: self.check_user_necessary_labels(a.user, a.group)
        }
        subactions[args.subaction](args)

    def _get_labels(self, entity):
        """
        Auxiliary function to get the metaparams/labels value of an entity.
        Implemented purely for convenience of not having to write
        this more complicated expression over and over again.
        """
        return entity.metaparams.get('labels', [])

    def _list_necessary_labels(self, entity, include_self=False):
        """
        Find labels that an entity needs to have based on its membership.
        This function is usually wrapped by one of the "public" methods
        defined below, rather than called directly.
        :param FreeIPAEntity entity: entity whose labels to list
        :param bool include_self: whether to include the entity's own labels
            (by default only nested entities' labels included)
        :returns: list of labels defined for nested groups (and entity itself)
        :rtype: [str]
        """
        labels = []
        for group in self.build_graph(entity):
            labels.extend(self._get_labels(group))
        if include_self:
            labels.extend(self._get_labels(entity))
        return labels

    def check_label_necessary(self, label, group):
        """
        Check if `label` is necessary for membership in `group`.
        :param str label: label value
        :param str group: name of the group to start the check from
        :returns: True if `label` is needed, False otherwise
        :rtype: bool
        :raises ManagerError: if `group` is not defined in config
        """
        group_entity = find_entity(self.entities, 'group', group)
        if not group_entity:
            raise ManagerError('Group %s does not exist in config' % group)
        labels = self._list_necessary_labels(group_entity, include_self=True)
        result = label in labels
        if result:
            self.lg.info('Label %s IS necessary for group %s', label, group)
        else:
            self.lg.info("Label %s ISN'T necessary for group %s", label, group)
        return result

    def list_user_missing_labels(self, user):
        """
        List labels that a user is missing and is expected to have
        based on their group membership.
        :param str user: name of user whose labels to check
        :returns: set of labels that `user` is missing
        :rtype: {str}
        :raises ManagerError: if `user` is not defined in config
        """
        user_entity = find_entity(self.entities, 'user', user)
        if not user_entity:
            raise ManagerError('User %s does not exist in config' % user)
        necessary = set(self.list_necessary_labels(user_entity))
        current = set(self._get_labels(user_entity))
        missing = necessary.difference(current)
        if missing:
            self.lg.info('User %s misses labels: {%s}',
                         user, ', '.join(missing))
        else:
            self.lg.info('User %s misses NO labels', user)
        return missing

    def list_necessary_labels(self, group):
        """
        Find labels that an entity needs to have based on its membership.
        Serves as wrapper around the related private method
        (plus entity resolution based on group name).
        :param str group: name of group whose labels to list
        :returns: list of labels defined for nested groups (and entity itself)
        :rtype: [str]
        :raises ManagerError: if `group` is not defined in config
        """
        group_entity = find_entity(self.entities, 'group', group)
        if not group_entity:
            raise ManagerError('Group %s does not exist in config' % group)
        labels = self._list_necessary_labels(group_entity, include_self=True)
        if labels:
            self.lg.info('Group %s requires labels: [%s]',
                         group, ', '.join(labels))
        else:
            self.lg.info('Group %s requires NO labels', group)
        return labels

    def check_user_necessary_labels(self, user, group):
        """
        Check if `user` has all the necessary labels for membership in `group`.
        :param str name: name of the user to check
        :param str group: name of the group to check
        :returns: True if `user ` has all required labels, False otherwise
        :rtype: bool
        :raises ManagerError: if `user` or `group` is not defined in config
        """
        user_entity = find_entity(self.entities, 'user', user)
        if not user_entity:
            raise ManagerError('User %s does not exist in config' % user)
        group_entity = find_entity(self.entities, 'group', group)
        if not group_entity:
            raise ManagerError('Group %s does not exist in config' % group)
        user_labels = self._get_labels(user_entity)
        required = self._list_necessary_labels(group_entity, include_self=True)
        result = all(label in user_labels for label in required)
        if result:
            self.lg.info('User %s DOES have all required labels for group %s',
                         user, group)
        else:
            self.lg.info('User %s DOES NOT have required labels for group %s',
                         user, group)
        return result


def load_query_tool(config, settings=None):
    """
    Initialize and return a QueryTool instance.
    This function serves as a wrapper for easy import into other scripts.
    :param str config: path to the config repository folder
    :param str settings: path to the settings file
    :returns: QueryTool instance that was initialized
    :rtype: QueryTool
    """
    querytool = QueryTool(config, settings)
    querytool.load()
    return querytool


def _parse_args(args=None):
    common = _args_common()
    parser = argparse.ArgumentParser(description='FreeIPA Manager Query')
    actions = parser.add_subparsers(help='query action to execute')

    member = actions.add_parser('member', parents=[common])
    member.add_argument(
        '-m', '--members', nargs='+', type=_entity_type, default=[],
        required=True, help='members (type:name)')
    member.add_argument(
        '-e', '--entities', nargs='+', type=_entity_type, default=[],
        required=True, help='entities whose members to check (type:name)')
    member.set_defaults(action='member')

    labels = actions.add_parser('labels')
    labels.set_defaults(action='labels')
    labels_actions = labels.add_subparsers(help='labels query action')

    labels_check = labels_actions.add_parser('check', parents=[common])
    labels_check.set_defaults(subaction='check')
    labels_check.add_argument('label', help='label value')
    labels_check.add_argument('group', help='group name')

    labels_missing = labels_actions.add_parser('missing', parents=[common])
    labels_missing.set_defaults(subaction='missing')
    labels_missing.add_argument('user', help='user name')

    labels_necessary = labels_actions.add_parser('necessary', parents=[common])
    labels_necessary.set_defaults(subaction='necessary')
    labels_necessary.add_argument('group', help='group name')

    labels_user = labels_actions.add_parser('user', parents=[common])
    labels_user.set_defaults(subaction='user')
    labels_user.add_argument('user', help='user name')
    labels_user.add_argument('group', help='group name')

    args = parser.parse_args(args)
    args.loglevel = _type_verbosity(args.loglevel)
    return args


def _entity_type(value):
    """
    Type function used for parsing --members/--entities arguments
    from colon-separated values into a list of (type, name) 2-tuples.
    """
    entity_type, entity_name = value.split(':')
    return entity_type, entity_name


def main():
    """
    Main executable function used when run as a command-line script.
    """
    args = _parse_args()
    querytool = QueryTool(args.config, args.settings, args.loglevel)
    querytool.load()
    querytool.run(args)


if __name__ == '__main__':
    main()

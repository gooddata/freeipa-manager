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

    def run(self, action, *args):
        """
        Run a query action based on arguments.
        :param str action: action to perform (membership/security check)
        :param [obj] args: arguments to pass to the action method
        """
        if action == 'member':
            self._query_membership(*args)

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
    querytool.run(args.action, args.members, args.entities)


if __name__ == '__main__':
    main()

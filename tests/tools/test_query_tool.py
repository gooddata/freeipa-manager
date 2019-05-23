#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.

import argparse
import logging
import mock
import os
import pytest
import re
from testfixtures import LogCapture, log_capture

import ipamanager.tools.query_tool as tool
import ipamanager.entities as entities
testdir = os.path.dirname(__file__)

modulename = 'ipamanager.tools.query_tool'
CONFIG_CORRECT = os.path.join(testdir, '../freeipa-manager-config/correct')
SETTINGS = os.path.join(testdir, '../freeipa-manager-config/settings.yaml')


class TestQueryTool(object):
    def setup_method(self, method):
        if not method.func_name.startswith('test_init'):
            self.querytool = tool.QueryTool(CONFIG_CORRECT, SETTINGS)
            if not re.match(r'^test_(run|load)', method.func_name):
                with LogCapture():
                    self.querytool.load()
            self.querytool.graph = {}
            self.querytool.ancestors = {}
            self.querytool.paths = {}

    @mock.patch('%s.load_settings' % modulename)
    def test_init(self, mock_load_settings):
        querytool = tool.QueryTool(CONFIG_CORRECT, SETTINGS)
        mock_load_settings.assert_called_with(SETTINGS)
        assert querytool.settings == mock_load_settings.return_value

    @mock.patch('%s.load_settings' % modulename)
    def test_init_no_settings(self, mock_load_settings):
        tool.QueryTool(CONFIG_CORRECT)
        mock_load_settings.assert_called_with(os.path.join(
            testdir, '../freeipa-manager-config/correct/settings_common.yaml'))

    def test_run(self):
        self.querytool._query_membership = mock.Mock()
        self.querytool.run('member', [], [])
        self.querytool._query_membership.assert_called_with([], [])

    @log_capture()
    @mock.patch('%s.IntegrityChecker' % modulename)
    @mock.patch('%s.ConfigLoader' % modulename)
    def test_load(self, mock_loader, mock_checker, log):
        self.querytool.load()
        mock_loader.assert_called_with(
            self.querytool.config, self.querytool.settings)
        mock_load = mock_loader.return_value.load
        mock_load.assert_called_with()
        assert self.querytool.entities == mock_load.return_value
        mock_checker.assert_called_with(
            self.querytool.entities, self.querytool.settings)
        mock_checker.return_value.check.assert_called_with()
        log.check(
            ('QueryTool', 'INFO', 'Running pre-query config load & checks'),
            ('QueryTool', 'INFO', 'Pre-query config load & checks finished'))

    def test_resolve_entities(self):
        entity_list = [('user', 'firstname.lastname'), ('group', 'group-two')]
        result = self.querytool._resolve_entities(entity_list)
        assert len(result) == 2
        assert isinstance(result[0], entities.FreeIPAUser)
        assert result[0].name == 'firstname.lastname'
        assert isinstance(result[1], entities.FreeIPAUserGroup)
        assert result[1].name == 'group-two'

    def test_resolve_entities_not_found(self):
        entity_list = [('user', 'firstname.lastname'), ('group', 'not-exist')]
        with pytest.raises(tool.ManagerError) as exc:
            self.querytool._resolve_entities(entity_list)
        assert exc.value[0] == 'group not-exist not found in config'

    @log_capture()
    def test_build_graph(self, log):
        entity = self.querytool.entities['user']['firstname.lastname']
        assert {repr(i) for i in self.querytool.build_graph(entity)} == {
            'group group-one-users', 'group group-two',
            'group group-three-users'}
        assert dict((repr(k), set(map(repr, v)))
                    for k, v in self.querytool.graph.iteritems()) == {
            'group group-one-users': {'group group-two',
                                      'group group-three-users'},
            'group group-three-users': set(),
            'group group-two': {'group group-three-users'},
            'user firstname.lastname': {'group group-one-users',
                                        'group group-two',
                                        'group group-three-users'}}
        assert dict((repr(k), map(repr, v))
                    for k, v in self.querytool.ancestors.iteritems()) == {
            'group group-one-users': ['user firstname.lastname'],
            'group group-three-users': ['group group-two'],
            'group group-two': ['group group-one-users']}
        log.check(('QueryTool', 'DEBUG',
                   'Calculating membership graph for firstname.lastname'),
                  ('QueryTool', 'DEBUG',
                   'Calculating membership graph for group-one-users'),
                  ('QueryTool', 'DEBUG',
                   'Calculating membership graph for group-two'),
                  ('QueryTool', 'DEBUG',
                   'Calculating membership graph for group-three-users'),
                  ('QueryTool', 'DEBUG',
                   'Found 0 entities for group-three-users'),
                  ('QueryTool', 'DEBUG',
                   'Found 1 entities for group-two'),
                  ('QueryTool', 'DEBUG',
                   'Found 2 entities for group-one-users'),
                  ('QueryTool', 'DEBUG',
                   'Found 3 entities for firstname.lastname'))

    @log_capture(level=logging.INFO)
    def test_check_membership(self, log):
        member = self.querytool.entities['user']['firstname.lastname2']
        entity = self.querytool.entities['group']['group-three-users']
        paths = self.querytool.check_membership(member, entity)
        assert len(paths) == 2
        assert [repr(i) for i in paths[0]] == [
            'user firstname.lastname2', 'group group-three-users']
        assert [repr(i) for i in paths[1]] == [
            'user firstname.lastname2', 'group group-four-users',
            'group group-three-users']
        log.check(
            ('QueryTool', 'INFO',
             ('firstname.lastname2 IS a member of group-three-users; '
              'possible paths: [user firstname.lastname2 -> group '
              'group-three-users; user firstname.lastname2 -> group '
              'group-four-users -> group group-three-users]')))

    def test_query_membership(self):
        members = [('user', 'firstname.lastname2'),
                   ('group', 'group-one-users')]
        entity_list = [('group', 'group-one-users'),
                       ('group', 'group-two'),
                       ('group', 'group-three-users')]
        self.querytool.check_membership = mock.Mock()
        self.querytool._query_membership(members, entity_list)
        assert [tuple(repr(i) for i in j.args) for j
                in self.querytool.check_membership.call_args_list] == [
            ('user firstname.lastname2', 'group group-one-users'),
            ('user firstname.lastname2', 'group group-two'),
            ('user firstname.lastname2', 'group group-three-users'),
            ('group group-one-users', 'group group-one-users'),
            ('group group-one-users', 'group group-two'),
            ('group group-one-users', 'group group-three-users')]

    @log_capture()
    def test_construct_path(self):
        members = [('user', 'firstname.lastname'),
                   ('group', 'group-one-users')]
        entity_list = [('group', 'group-one-users'),
                       ('group', 'group-two'),
                       ('group', 'group-three-users')]
        self.querytool._query_membership(members, entity_list)
        entity = self.querytool.entities['group']['group-two']
        member = self.querytool.entities['user']['firstname.lastname']
        paths = self.querytool._construct_path(entity, member)
        assert len(paths) == 1
        assert map(repr, paths[0]) == [
            'user firstname.lastname', 'group group-one-users',
            'group group-two']

    @log_capture()
    def test_construct_path_non_member(self):
        members = [('user', 'firstname.lastname2'),
                   ('group', 'group-one-users')]
        entity_list = [('group', 'group-one-users'),
                       ('group', 'group-two'),
                       ('group', 'group-three-users')]
        self.querytool._query_membership(members, entity_list)
        entity = self.querytool.entities['group']['group-two']
        member = self.querytool.entities['user']['firstname.lastname2']
        assert self.querytool._construct_path(entity, member) == []

    def _mock_find(self, *missing):
        def f(entities, entity_type, name):
            for t, n in missing:
                if t == entity_type and n == name:
                    return None
            return 'mock_entity: <%s %s>' % (entity_type, name)
        return f

    def test_check_user_membership(self):
        self.querytool.check_membership = mock.Mock()
        self.querytool.check_membership.return_value = [['user1', 'group-one']]
        with mock.patch('%s.find_entity' % modulename, self._mock_find()):
            ret = self.querytool.check_user_membership('user1', 'group-one')
        self.querytool.check_membership.assert_called_with(
            'mock_entity: <user user1>', 'mock_entity: <group group-one>')
        assert ret

    def test_check_user_membership_not_a_member(self):
        self.querytool.check_membership = mock.Mock()
        self.querytool.check_membership.return_value = []
        with mock.patch('%s.find_entity' % modulename, self._mock_find()):
            ret = self.querytool.check_user_membership('user1', 'group-one')
        self.querytool.check_membership.assert_called_with(
            'mock_entity: <user user1>', 'mock_entity: <group group-one>')
        assert not ret

    def test_check_user_membership_user_not_found(self):
        mock_find_inst = self._mock_find(('user', 'user1'))
        with mock.patch('%s.find_entity' % modulename, mock_find_inst):
            with pytest.raises(tool.ManagerError) as exc:
                self.querytool.check_user_membership('user1', 'group-one')
        assert exc.value[0] == 'User user1 does not exist in config'

    def test_check_user_membership_group_not_found(self):
        mock_find_inst = self._mock_find(('group', 'group-one'))
        with mock.patch('%s.find_entity' % modulename, mock_find_inst):
            with pytest.raises(tool.ManagerError) as exc:
                self.querytool.check_user_membership('user1', 'group-one')
        assert exc.value[0] == 'Group group-one does not exist in config'

    def test_list_groups(self):
        self.querytool.build_graph = mock.Mock()
        self.querytool.build_graph.return_value = set()
        for i in range(5):
            mock_group = mock.Mock()
            mock_group.name = 'group%d' % i
            self.querytool.build_graph.return_value.add(mock_group)
        with mock.patch('%s.find_entity' % modulename, self._mock_find()):
            ret = self.querytool.list_groups('user1')
        self.querytool.build_graph.assert_called_with(
            'mock_entity: <user user1>')
        assert ret.__class__.__name__ == 'generator'
        assert set(ret) == set('group%d' % i for i in range(5))

    def test_list_groups_user_not_found(self):
        with mock.patch('%s.find_entity' % modulename) as mock_find:
            mock_find.return_value = None
            with pytest.raises(tool.ManagerError) as exc:
                self.querytool.list_groups('user1')
        assert exc.value[0] == 'User user1 does not exist in config'


class TestQueryToolTopLevel(object):
    @mock.patch('%s.QueryTool' % modulename)
    def test_load_query_tool(self, mock_querytool):
        querytool = tool.load_query_tool('config', 'settings')
        assert querytool == mock_querytool.return_value
        querytool.load.assert_called_with()

    def test_entity_type(self):
        assert tool._entity_type(
            'sometype:somename') == ('sometype', 'somename')

    def test_entity_type_error_too_few_values(self):
        with pytest.raises(ValueError) as exc:
            tool._entity_type('sometype,somename')
        assert exc.value[0] == 'need more than 1 value to unpack'

    def test_entity_type_error_too_many_values(self):
        with pytest.raises(ValueError) as exc:
            tool._entity_type('sometype:somename:something')
        assert exc.value[0] == 'too many values to unpack'

    def test_parse_args(self):
        assert tool._parse_args([
            'member', 'config', '-m', 'group:group1', 'user:user1',
            '-e', 'group:group2', '-v', '-s', 'settings.yam'
        ]) == argparse.Namespace(
            action='member', config='config', loglevel=logging.INFO,
            members=[('group', 'group1'), ('user', 'user1')],
            pull_types=['user'], settings='settings.yam',
            entities=[('group', 'group2')])

    @mock.patch('%s.QueryTool' % modulename)
    @mock.patch('%s._parse_args' % modulename)
    def test_main(self, mock_parse_args, mock_querytool):
        mock_parse_args.return_value = argparse.Namespace(
            action='member', config='config', loglevel=20,
            members=[('group', 'group1'), ('user', 'user1')],
            pull_types=['user'], settings='settings.yam',
            entities=[('group', 'group2')])
        tool.main()
        mock_querytool.assert_called_with('config', 'settings.yam', 20)
        mock_querytool.return_value.load.assert_called_with()
        mock_querytool.return_value.run.assert_called_with(
            'member', [('group', 'group1'), ('user', 'user1')],
            [('group', 'group2')])

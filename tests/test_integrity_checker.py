#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.

import logging
import mock
import os.path
import pytest
from testfixtures import log_capture

from _utils import _import
tool = _import('ipamanager', 'integrity_checker')
testpath = os.path.dirname(os.path.abspath(__file__))


class TestIntegrityChecker(object):
    def _create_checker(self, entities):
        settings = {'user-group-pattern': '^role-.+|.+-users$'}
        self.checker = tool.IntegrityChecker(entities, settings)
        self.checker.errs = dict()

    def test_build_dict(self):
        self._create_checker(self._sample_entities_correct())
        entity_dict = self.checker.entity_dict
        assert sorted(entity_dict.keys()) == [
            'group', 'hbacrule', 'hostgroup', 'permission', 'privilege',
            'role', 'service', 'sudorule', 'user']
        assert isinstance(
            entity_dict['hostgroup']['group-one-hosts'],
            tool.entities.FreeIPAHostGroup)
        assert isinstance(
            entity_dict['group']['group-one-users'],
            tool.entities.FreeIPAUserGroup)
        assert isinstance(
            entity_dict['user']['firstname.lastname3'],
            tool.entities.FreeIPAUser)
        assert isinstance(
            entity_dict['role']['role-one'],
            tool.entities.FreeIPARole)
        assert isinstance(
            entity_dict['service']['service-one'],
            tool.entities.FreeIPAService)
        assert isinstance(
            entity_dict['privilege']['privilege-one'],
            tool.entities.FreeIPAPrivilege)
        assert isinstance(
            entity_dict['permission']['permission-one'],
            tool.entities.FreeIPAPermission)

    @log_capture('IntegrityChecker', level=logging.WARNING)
    def test_check_empty(self, captured_warnings):
        self._create_checker(dict())
        self.checker.check()
        captured_warnings.check((
            'IntegrityChecker', 'WARNING',
            'No entities to check for integrity'))

    def test_check_correct_no_nesting_limit(self):
        self._create_checker(self._sample_entities_correct())
        self.checker._check_nesting_level = mock.Mock()
        self.checker.check()
        assert not self.checker.errs
        self.checker._check_nesting_level.assert_not_called()

    def test_check_memberof_nonexistent(self):
        self._create_checker(self._sample_entities_member_nonexistent())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('group', 'group-two'): ['memberOf non-existent group group-one'],
            ('hostgroup', 'group-one-hosts'): [
                'memberOf non-existent hostgroup group-two'],
            ('user', 'firstname.lastname2'): [
                'memberOf non-existent group group-one'],
            ('service', 'service-two'): [
                'memberOf non-existent role role-one']}

    def test_check_memberof_meta_violation(self):
        data = {
            'group': {'group-one': tool.entities.FreeIPAUserGroup(
                      'group-one', {}, 'path')},
            'user': {'user.one': tool.entities.FreeIPAUser('user.one', {
                     'firstName': 'User', 'lastName': 'One',
                     'memberOf': {'group': ['group-one']}}, 'path2')}}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('user', 'user.one'): ['group-one cannot contain users directly']}

    def test_check_rule_member_nonexistent(self):
        data = {
            'hbacrule': {'rule-one': tool.entities.FreeIPAHBACRule(
                'rule-one', {'memberHost': ['no'],
                             'memberUser': ['no']}, 'path')}}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('hbacrule', 'rule-one'): [
                'non-existent memberHost no',
                'non-existent memberUser no']}

    def test_check_rule_meta_violation(self):
        data = {
            'hbacrule': {
                'rule-one': tool.entities.FreeIPAHBACRule(
                    'rule-one', {
                        'memberHost': ['group-one-hosts'],
                        'memberUser': ['group-one-users']}, 'path')},
            'hostgroup': {'group-one-hosts': tool.entities.FreeIPAHostGroup(
                'group-one-hosts', {}, 'path')},
            'group': {'group-one-users': tool.entities.FreeIPAUserGroup(
                'group-one-users', {}, 'path')}}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('hbacrule', 'rule-one'): ['group-one-users can contain users']}

    def test_check_rule_member_missing_attribute(self):
        data = {
            'hbacrule': {'rule-one': tool.entities.FreeIPAHBACRule(
                         'rule-one', {}, 'path')}}
        self._create_checker(data)
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('hbacrule', 'rule-one'): ['no memberHost', 'no memberUser']}

    def test_check_memberof_invalidtype(self):
        self._create_checker(self._sample_entities_member_invalidtype())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('user', 'firstname.lastname2'): [
                "group-one can only have members of type ['hostgroup']"],
            ('permission', 'permission-one'): [
                ("role-one can only have members of type ['user', 'group', "
                 "'service', 'hostgroup']")],
            ('role', 'role-one'): [
                "permission-one can only have members of type ['privilege']"]}

    def test_check_user_invalid_manager(self):
        self._create_checker(self._sample_entities_user_invalid_manager())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {('user', 'firstname.lastname2'): [
                                     'manager karel.gott does not exist']}

    def test_check_memberof_itself(self):
        self._create_checker(self._sample_entities_member_itself())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('group', 'group-one'): ['memberOf itself']}

    def test_check_cycle_two_nodes(self):
        self._create_checker(self._sample_entities_cycle_two_nodes())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('group', 'group-one'): [
                'Cyclic membership: [group group-one, group group-two]'],
            ('group', 'group-two'): [
                'Cyclic membership: [group group-two, group group-one]']}

    def test_check_cycle_three_nodes(self):
        self._create_checker(self._sample_entities_cycle_three_nodes())
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('group', 'group-one'): [
                ('Cyclic membership: '
                 '[group group-one, group group-two, group group-three]')],
            ('group', 'group-three'): [
                ('Cyclic membership: '
                 '[group group-three, group group-one, group group-two]')],
            ('group', 'group-two'): [
                ('Cyclic membership: '
                 '[group group-two, group group-three, group group-one]')]}

    def test_check_nesting_limit_ok(self):
        self._create_checker(self._sample_entities_correct())
        self.checker.nesting_limit = 3
        self.checker.check()
        assert not self.checker.errs

    def test_check_nesting_limit_exceeded(self):
        self._create_checker(self._sample_entities_correct())
        self.checker.nesting_limit = 2
        with pytest.raises(tool.IntegrityError):
            self.checker.check()
        assert self.checker.errs == {
            ('group', 'group-one-users'): ['Nesting level exceeded: 3 > 2']}

    def test_check_member_type_ok(self):
        self._create_checker(dict())
        user_one = tool.entities.FreeIPAUser(
            'firstname.lastname',
            {'firstName': 'Firstname', 'lastName': 'Lastname',
             'memberOf': {'group': ['group-one-users']}})
        group_one = tool.entities.FreeIPAUserGroup('group-one', {})
        self.checker._check_member_type(user_one, group_one)

    def test_check_member_type_wrong_target_type_rule(self):
        self._create_checker(dict())
        user_one = tool.entities.FreeIPAUser(
            'firstname.lastname',
            {'firstName': 'Firstname', 'lastName': 'Lastname',
             'memberOf': {'group': ['group-one-users']}})
        rule_one = tool.entities.FreeIPAHBACRule('rule-one', {})
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker._check_member_type(user_one, rule_one)
        assert exc.value[0] == (
            "rule-one not one of (<class "
            "'ipamanager.entities.FreeIPAGroup'>, <class 'ipamanager.entities"
            ".FreeIPARole'>, <class 'ipamanager.entities.FreeIPAPrivilege'>, "
            "<class 'ipamanager.entities.FreeIPAPermission'>, <class 'ipamana"
            "ger.entities.FreeIPAHBACServiceGroup'>), cannot have members")

    def test_check_member_type_wrong_target_type_service(self):
        self._create_checker(dict())
        user_one = tool.entities.FreeIPAUser(
            'firstname.lastname',
            {'firstName': 'Firstname', 'lastName': 'Lastname',
             'memberOf': {'group': ['group-one-users']}})
        service_one = tool.entities.FreeIPAHBACRule('service-one', {})
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker._check_member_type(user_one, service_one)
        assert exc.value[0] == (
            "service-one not one of (<class 'ipamanager.entities.FreeIPAGroup'"
            ">, <class 'ipamanager.entities.FreeIPARole'>, <class 'ipamanager."
            "entities.FreeIPAPrivilege'>, <class 'ipamanager.entities."
            "FreeIPAPermission'>, <class 'ipamanager.entities.FreeIPAHBAC"
            "ServiceGroup'>), cannot have members")

    def test_check_member_type_wrong_member_type(self):
        self._create_checker(dict())
        user_one = tool.entities.FreeIPAHostGroup('hostgroup-one', {})
        group_one = tool.entities.FreeIPAUserGroup('group-one', {})
        with pytest.raises(tool.IntegrityError) as exc:
            self.checker._check_member_type(user_one, group_one)
        assert exc.value[0] == (
            "group-one can only have members of type ['user', 'group']")

    @log_capture('IntegrityChecker', level=logging.DEBUG)
    def test_check_nesting_level(self, captured_log):
        self._create_checker(self._sample_entities_correct())
        assert self.checker._check_nesting_level(
            'group', 'group-two') == 2
        assert self.checker.nesting == {
            'group': {'group-two': 2, 'group-three': 1, 'group-four': 0},
            'hostgroup': {}}
        assert self.checker._check_nesting_level(
            'group', 'group-one-users') == 3
        assert self.checker.nesting == {
            'group': {'group-one-users': 3, 'group-two': 2,
                      'group-three': 1, 'group-four': 0},
            'hostgroup': {}}
        captured_log.check(
            ('IntegrityChecker', 'DEBUG',
             'Checking nesting level for group group-two'),
            ('IntegrityChecker', 'DEBUG',
             'Checking nesting level for group group-three'),
            ('IntegrityChecker', 'DEBUG',
             'Checking nesting level for group group-four'),
            ('IntegrityChecker', 'DEBUG',
             'Nesting level of group group-four is 0'),
            ('IntegrityChecker', 'DEBUG',
             'Nesting level of group group-three is 1'),
            ('IntegrityChecker', 'DEBUG',
             'Nesting level of group group-two is 2'),
            ('IntegrityChecker', 'DEBUG',
             'Checking nesting level for group group-one-users'),
            ('IntegrityChecker', 'DEBUG',
             'Checking nesting level for group group-two'),
            ('IntegrityChecker', 'DEBUG',
             'Returning cached nesting level for group group-two (2)'),
            ('IntegrityChecker', 'DEBUG',
             'Nesting level of group group-one-users is 3'))

    def _sample_entities_correct(self):
        return {
            'user': {
                'firstname.lastname': tool.entities.FreeIPAUser(
                    'firstname.lastname',
                    {'firstName': 'Firstname', 'lastName': 'Lastname',
                     'manager': 'firstname.lastname2'}, 'path'),
                'firstname.lastname2': tool.entities.FreeIPAUser(
                    'firstname.lastname2',
                    {'firstName': 'Firstname', 'lastName': 'Lastname',
                     'memberOf': {'group': ['group-one-users'],
                                  'role': ['role-one']}}, 'path'),
                'firstname.lastname3': tool.entities.FreeIPAUser(
                    'firstname.lastname3',
                    {'firstName': 'Firstname', 'lastName': 'Lastname'},
                    'path')},
            'group': {
                'group-one-users': tool.entities.FreeIPAUserGroup(
                    'group-one-users', {
                        'memberOf': {'group': ['group-two'],
                                     'role': ['role-one']}}, 'path'),
                'group-two': tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'group': ['group-three']}}, 'path'),
                'group-three': tool.entities.FreeIPAUserGroup(
                    'group-three', {
                        'memberOf': {'group': ['group-four']}}, 'path'),
                'group-four': tool.entities.FreeIPAUserGroup(
                    'group-four', {}, 'path')},
            'hostgroup': {
                'group-one-hosts': tool.entities.FreeIPAHostGroup(
                    'group-one-hosts', {
                        'memberOf': {'hostgroup': ['group-two'],
                                     'role': ['role-one']}}, 'path'),
                'group-two': tool.entities.FreeIPAHostGroup(
                    'group-two', {}, 'path')},
            'hbacrule': {
                'rule-one': tool.entities.FreeIPAHBACRule(
                    'rule-one',
                    {'memberHost': ['group-two'], 'memberUser': ['group-two']},
                    'path')},
            'sudorule': {
                'rule-one': tool.entities.FreeIPASudoRule(
                    'rule-one',
                    {'memberHost': ['group-two'], 'memberUser': ['group-two']},
                    'path')},
            'service': {
                'service-one': tool.entities.FreeIPAService(
                    'service-one',
                    {'memberOf': {'role': ['role-one']}}, 'path')},
            'role': {
                'role-one': tool.entities.FreeIPARole(
                    'role-one', {
                        'memberOf': {'privilege': ['privilege-one']}}, 'path'),
                'role-two': tool.entities.FreeIPARole(
                    'role-two', {}, 'path')},
            'privilege': {
                'privilege-one': tool.entities.FreeIPAPrivilege(
                    'privilege-one', {
                        'memberOf': {'permission': ['permission-one']}},
                    'path'),
                'privilege-two': tool.entities.FreeIPAPrivilege(
                    'privilege-two', {}, 'path')},
            'permission': {
                'permission-one': tool.entities.FreeIPAPermission(
                    'permission-one', {}, 'path')}}

    def _sample_entities_member_nonexistent(self):
        return {
            'user': {
                'firstname.lastname': tool.entities.FreeIPAUser(
                    'firstname.lastname',
                    {'firstName': 'Firstname', 'lastName': 'Lastname'},
                    'path'),
                'firstname.lastname2': tool.entities.FreeIPAUser(
                    'firstname.lastname2',
                    {'firstName': 'Firstname', 'lastName': 'Lastname',
                     'memberOf': {'group': ['group-one']}}, 'path'),
                'firstname.lastname3': tool.entities.FreeIPAUser(
                    'firstname.lastname3',
                    {'firstName': 'Firstname', 'lastName': 'Lastname'},
                    'path')},
            'group': {
                'group-two': tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'group': ['group-one']}}, 'path')},
            'hostgroup': {
                'group-one-hosts': tool.entities.FreeIPAHostGroup(
                    'group-one-hosts', {
                        'memberOf': {'hostgroup': ['group-two']}}, 'path')},
            'service': {
                'service-two': tool.entities.FreeIPAService(
                    'service-two', {
                        'memberOf': {'role': ['role-one']}}, 'path')}}

    def _sample_entities_member_invalidtype(self):
        return {
            'user': {
                'firstname.lastname2': tool.entities.FreeIPAUser(
                    'firstname.lastname2',
                    {'firstName': 'Firstname', 'lastName': 'Lastname',
                     'memberOf': {'hostgroup': ['group-one']}}, 'path')},
            'hostgroup': {'group-one': tool.entities.FreeIPAHostGroup(
                          'group-one', {}, 'path')},
            'role': {'role-one': tool.entities.FreeIPARole(
                'role-one', {'memberOf': {'permission': ['permission-one']}},
                'path')},
            'permission': {
                'permission-one': tool.entities.FreeIPAPermission(
                    'permission-one', {'memberOf': {'role': ['role-one']}},
                    'path')}}

    def _sample_entities_user_invalid_manager(self):
        return {
            'user': {
                'firstname.lastname2': tool.entities.FreeIPAUser(
                    'firstname.lastname2',
                    {'firstName': 'Firstname', 'lastName': 'Lastname',
                     'manager': 'karel.gott'}, 'path')}}

    def _sample_entities_member_itself(self):
        return {
            'group': {
                'group-one': tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'group': ['group-one']}}, 'path')}}

    def _sample_entities_cycle_two_nodes(self):
        return {
            'group': {
                'group-one': tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'group': ['group-two']}}, 'path'),
                'group-two': tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'group': ['group-one']}}, 'path')}}

    def _sample_entities_cycle_three_nodes(self):
        return {
            'group': {
                'group-one': tool.entities.FreeIPAUserGroup(
                    'group-one', {
                        'memberOf': {'group': ['group-two']}}, 'path'),
                'group-two': tool.entities.FreeIPAUserGroup(
                    'group-two', {
                        'memberOf': {'group': ['group-three']}}, 'path'),
                'group-three': tool.entities.FreeIPAUserGroup(
                    'group-three', {
                        'memberOf': {'group': ['group-one']}}, 'path')}}

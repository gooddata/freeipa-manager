#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.

import logging
import os.path
import pytest
from testfixtures import log_capture

from _utils import _import
tool = _import('ipamanager', 'config_loader')
entities = _import('ipamanager', 'entities')
utils = _import('ipamanager', 'utils')
modulename = 'ipamanager.config_loader'
testpath = os.path.dirname(os.path.abspath(__file__))

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')
CONFIG_INVALID = os.path.join(testpath, 'freeipa-manager-config/invalid')
NUMBERS = ['one', 'three', 'two']


class TestConfigLoader(object):
    def setup_method(self, method):
        if method.func_name.startswith('test_load'):
            ignored = {
                'user': ['firstname.lastname$'],
                'group': ['group-one-users'],
                'hostgroup': ['some-hostgroup']
            }
        else:
            ignored = {}
        self.loader = tool.ConfigLoader(CONFIG_CORRECT, {'ignore': ignored})
        self.expected_hostgroups = [
            CONFIG_CORRECT + '/hostgroups/group_%s.yaml' % group
            for group in NUMBERS]
        self.expected_users = [
            CONFIG_CORRECT + '/users/%s.yaml' % user
            for user in [
                'firstname_lastname', 'firstname_lastname_2', 'test_user']]
        self.expected_groups = [
            CONFIG_CORRECT + '/groups/group_%s.yaml' % group
            for group in ['four'] + NUMBERS]
        self.expected_hbac_rules = [
            CONFIG_CORRECT + '/hbacrules/rule_%s.yaml' % rule
            for rule in NUMBERS]
        self.expected_hbac_svc = [
            CONFIG_CORRECT + '/hbacsvcs/hbacsvc-%s.yaml' % rule
            for rule in NUMBERS]
        self.expected_hbac_svcgroup = [
            CONFIG_CORRECT + '/hbacsvcgroups/hbacsvcgroup-%s.yaml' % rule
            for rule in NUMBERS]
        self.expected_sudo_rules = [
            CONFIG_CORRECT + '/sudorules/rule_%s.yaml' % rule
            for rule in NUMBERS]
        self.expected_roles = [
            CONFIG_CORRECT + '/roles/role_%s.yaml' % role
            for role in NUMBERS]
        self.expected_privileges = [
            CONFIG_CORRECT + '/privileges/privilege_%s.yaml' % privilege
            for privilege in NUMBERS]
        self.expected_permissions = [
            CONFIG_CORRECT + '/permissions/permission_%s.yaml' % permission
            for permission in NUMBERS]
        self.expected_services = [
            CONFIG_CORRECT + '/services/service_%s.yaml' % service
            for service in NUMBERS]
        for cls in utils.ENTITY_CLASSES:
            cls.ignored = []

    def test_retrieve_paths(self):
        paths = self.loader._retrieve_paths()
        assert sorted(paths.keys()) == [
            'group', 'hbacrule', 'hbacsvc', 'hbacsvcgroup', 'hostgroup',
            'permission', 'privilege', 'role', 'service', 'sudorule', 'user']
        assert sorted(paths['hostgroup']) == self.expected_hostgroups
        assert sorted(paths['user']) == self.expected_users
        assert sorted(paths['hbacsvc']) == self.expected_hbac_svc
        assert sorted(paths['hbacsvcgroup']) == self.expected_hbac_svcgroup
        assert sorted(paths['group']) == self.expected_groups
        assert sorted(paths['hbacrule']) == self.expected_hbac_rules
        assert sorted(paths['sudorule']) == self.expected_sudo_rules
        assert sorted(paths['role']) == self.expected_roles
        assert sorted(paths['privilege']) == self.expected_privileges
        assert sorted(paths['permission']) == self.expected_permissions
        assert sorted(paths['service']) == self.expected_services

    @log_capture('ConfigLoader', level=logging.INFO)
    def test_retrieve_paths_empty(self, captured_log):
        self.loader.basepath = '/dev/null'
        paths = self.loader._retrieve_paths()
        assert paths.keys() == []
        assert set(i.msg % i.args for i in captured_log.records) == set([
            'No hbacrule files found',
            'No hbacsvc files found',
            'No hbacsvcgroup files found',
            'No hostgroup files found',
            'No sudorule files found',
            'No group files found',
            'No user files found',
            'No role files found',
            'No service files found',
            'No privilege files found',
            'No permission files found'])

    @log_capture('ConfigLoader', level=logging.DEBUG)
    def test_run_yamllint_check_ok(self, captured_log):
        data = '---\ntest-group:\n  description: A test group.\n'
        tool.run_yamllint_check(data)
        captured_log.check()

    @log_capture('ConfigLoader', level=logging.DEBUG)
    def test_run_yamllint_check_long_line(self, captured_log):
        data = '---\ntest-group:\n  description: %s\n' % ('x' * 80)
        tool.run_yamllint_check(data)
        captured_log.check()

    def test_run_yamllint_check_error(self):
        data = 'test-group:\n  description: A test group.\n  description: test'
        with pytest.raises(tool.ConfigError) as exc:
            tool.run_yamllint_check(data)
        assert exc.value[0] == (
            'yamllint errors: [1:1: missing document start "---" '
            '(document-start), 3:3: duplication of key "description" '
            'in mapping (key-duplicates), 3:20: no new line character '
            'at the end of file (new-line-at-end-of-file)]')

    def test_parse(self):
        self.loader.entities = {'user': {}}
        data = {'test.user': {'firstName': 'first', 'lastName': 'last'}}
        self.loader._parse(
            data, entities.FreeIPAUser,
            '%s/users/test_user.yaml' % CONFIG_CORRECT)
        assert self.loader.entities.keys() == ['user']
        assert len(self.loader.entities['user']) == 1
        assert isinstance(self.loader.entities['user']['test.user'],
                          entities.FreeIPAUser)

    def test_parse_empty(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._parse(
                {}, entities.FreeIPAUser,
                '%s/users/test_user.yaml' % CONFIG_CORRECT)
        assert exc.value[0] == 'Config must be a non-empty dictionary'

    def test_parse_bad_data_format(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._parse(
                [{'test.user': {}}], entities.FreeIPAUser,
                '%s/users/test_user.yaml' % CONFIG_CORRECT)
        assert exc.value[0] == 'Config must be a non-empty dictionary'

    def test_parse_duplicit_entities(self):
        data = {'test.user': {'firstName': 'first', 'lastName': 'last'}}
        self.loader.entities = {
            'user': {'test.user': entities.FreeIPAUser(
                'test.user', {'firstName': 'first', 'lastName': 'last'})}}
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._parse(
                data, entities.FreeIPAUser,
                '%s/users/test_user.yaml' % CONFIG_CORRECT)
        assert exc.value[0] == 'Duplicit definition of user test.user'

    def test_parse_two_entities_in_file(self):
        data = {
            'test.user': {'firstName': 'first', 'lastName': 'last'},
            'test.user2': {'firstName': 'first', 'lastName': 'last'}}
        self.loader.entities = {'user': dict()}
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._parse(
                data, entities.FreeIPAUser,
                '%s/users/test_user.yaml' % CONFIG_CORRECT)
        assert exc.value[0] == (
            'More than one entity parsed from users/test_user.yaml (2)'
        )

    @log_capture('ConfigLoader', level=logging.INFO)
    def test_parse_ignored(self, captured_log):
        data = {'test.user': {'firstName': 'first', 'lastName': 'last'}}
        self.loader.entities['user'] = []
        self.loader.ignored['user'] = ['test.user']
        self.loader._parse(
            data, entities.FreeIPAUser,
            '%s/users/test_user.yaml' % CONFIG_CORRECT)
        assert self.loader.entities['user'] == []
        captured_log.check(('ConfigLoader', 'INFO',
                            ('Not creating ignored user test.user '
                             'from users/test_user.yaml')))

    @log_capture('ConfigLoader', level=logging.INFO)
    def test_load(self, captured_log):
        self.loader.basepath = CONFIG_CORRECT
        self.loader.load()
        hostgroups = self.loader.entities['hostgroup']
        assert len(hostgroups) == 3
        assert set(hostgroups.keys()) == set([
            'group-one-hosts', 'group-two', 'group-three-hosts'])
        users = self.loader.entities['user']
        assert len(users) == 2
        assert set(users.keys()) == set([
            'test.user', 'firstname.lastname2'])
        hbacsvc = self.loader.entities['hbacsvc']
        assert len(hbacsvc) == 3
        assert set(hbacsvc.keys()) == set([
            'hbacsvc-one', 'hbacsvc-two', 'hbacsvc-three'])
        hbacsvcgroup = self.loader.entities['hbacsvcgroup']
        assert len(hbacsvcgroup) == 3
        assert set(hbacsvcgroup.keys()) == set([
            'hbacsvcgroup-one', 'hbacsvcgroup-two', 'hbacsvcgroup-three'])
        groups = self.loader.entities['group']
        assert len(groups) == 3
        assert set(groups.keys()) == set(
            ['group-two', 'group-three-users', 'group-four-users'])
        service = self.loader.entities['service']
        assert len(service) == 3
        assert set(service.keys()) == set([
            'service-one', 'service-two', 'service-three'])
        privilege = self.loader.entities['privilege']
        assert len(privilege) == 3
        assert set(privilege.keys()) == set([
            'privilege-one', 'privilege-two', 'privilege-three'])
        permission = self.loader.entities['permission']
        assert len(permission) == 3
        assert set(permission.keys()) == set([
            'permission-one', 'permission-two', 'permission-three'])
        role = self.loader.entities['role']
        assert len(role) == 3
        assert set(role.keys()) == set([
            'role-one', 'role-two', 'role-three'])
        captured_log.check(
            ('ConfigLoader', 'INFO',
             'Checking local configuration at %s' % CONFIG_CORRECT),
            ('ConfigLoader', 'INFO', 'Parsed 3 hbacrules'),
            ('ConfigLoader', 'INFO', 'Parsed 3 hbacsvcs'),
            ('ConfigLoader', 'INFO', 'Parsed 3 hbacsvcgroups'),
            ('ConfigLoader', 'INFO', 'Parsed 3 hostgroups'),
            ('ConfigLoader', 'INFO', 'Parsed 3 permissions'),
            ('ConfigLoader', 'INFO', 'Parsed 3 privileges'),
            ('ConfigLoader', 'INFO', 'Parsed 3 roles'),
            ('ConfigLoader', 'INFO', 'Parsed 3 services'),
            ('ConfigLoader', 'INFO', 'Parsed 3 sudorules'),
            ('ConfigLoader', 'INFO',
             ('Not creating ignored user firstname.lastname '
              'from users/firstname_lastname.yaml')),
            ('ConfigLoader', 'INFO', 'Parsed 2 users'),
            ('ConfigLoader', 'INFO',
             ('Not creating ignored group group-one-users '
              'from groups/group_one.yaml')),
            ('ConfigLoader', 'INFO', 'Parsed 3 groups'))

    @log_capture('ConfigLoader', level=logging.INFO)
    def test_load_no_apply_ignored(self, captured_log):
        self.loader.basepath = CONFIG_CORRECT
        self.loader.ignore = False
        self.loader.load()
        hostgroups = self.loader.entities['hostgroup']
        assert len(hostgroups) == 3
        assert set(hostgroups.keys()) == set([
            'group-one-hosts', 'group-two', 'group-three-hosts'])
        users = self.loader.entities['user']
        assert len(users) == 3
        assert set(users.keys()) == set([
            'test.user', 'firstname.lastname', 'firstname.lastname2'])
        hbacsvc = self.loader.entities['hbacsvc']
        assert len(hbacsvc) == 3
        assert set(hbacsvc.keys()) == set([
            'hbacsvc-one', 'hbacsvc-two', 'hbacsvc-three'])
        hbacsvcgroup = self.loader.entities['hbacsvcgroup']
        assert len(hbacsvcgroup) == 3
        assert set(hbacsvcgroup.keys()) == set([
            'hbacsvcgroup-one', 'hbacsvcgroup-two', 'hbacsvcgroup-three'])
        groups = self.loader.entities['group']
        assert len(groups) == 4
        assert set(groups.keys()) == set([
            'group-one-users', 'group-two',
            'group-three-users', 'group-four-users'])
        service = self.loader.entities['service']
        assert len(service) == 3
        assert set(service.keys()) == set([
            'service-one', 'service-two', 'service-three'])
        privilege = self.loader.entities['privilege']
        assert len(privilege) == 3
        assert set(privilege.keys()) == set([
            'privilege-one', 'privilege-two', 'privilege-three'])
        permission = self.loader.entities['permission']
        assert len(permission) == 3
        assert set(permission.keys()) == set([
            'permission-one', 'permission-two', 'permission-three'])
        role = self.loader.entities['role']
        assert len(role) == 3
        assert set(role.keys()) == set([
            'role-one', 'role-two', 'role-three'])
        captured_log.check(
            ('ConfigLoader', 'INFO',
             'Checking local configuration at %s' % CONFIG_CORRECT),
            ('ConfigLoader', 'INFO', 'Parsed 3 hbacrules'),
            ('ConfigLoader', 'INFO', 'Parsed 3 hbacsvcs'),
            ('ConfigLoader', 'INFO', 'Parsed 3 hbacsvcgroups'),
            ('ConfigLoader', 'INFO', 'Parsed 3 hostgroups'),
            ('ConfigLoader', 'INFO', 'Parsed 3 permissions'),
            ('ConfigLoader', 'INFO', 'Parsed 3 privileges'),
            ('ConfigLoader', 'INFO', 'Parsed 3 roles'),
            ('ConfigLoader', 'INFO', 'Parsed 3 services'),
            ('ConfigLoader', 'INFO', 'Parsed 3 sudorules'),
            ('ConfigLoader', 'INFO', 'Parsed 3 users'),
            ('ConfigLoader', 'INFO', 'Parsed 4 groups'))

    @log_capture('ConfigLoader', level=logging.INFO)
    def test_load_empty(self, captured_log):
        self.loader.basepath = '/dev/null'
        self.loader.load()
        assert self.loader.entities == {
            'group': {}, 'hbacrule': {}, 'hbacsvc': {}, 'hbacsvcgroup': {},
            'hostgroup': {}, 'sudorule': {}, 'user': {},
            'permission': {}, 'privilege': {}, 'role': {}, 'service': {}}
        assert set(i.msg % i.args for i in captured_log.records) == set([
            'Checking local configuration at /dev/null',
            'No hbacrule files found',
            'No hbacsvc files found',
            'No hbacsvcgroup files found',
            'No hostgroup files found',
            'No sudorule files found',
            'No group files found',
            'No service files found',
            'No privilege files found',
            'No role files found',
            'No permission files found',
            'No user files found'])

    def test_load_invalid(self):
        self.loader.basepath = CONFIG_INVALID
        with pytest.raises(tool.ConfigError) as exc:
            self.loader.load()
        assert exc.value[0] == (
            'There have been errors in 18 configuration files: '
            '[hbacrules/extrakey.yaml, hbacsvcgroups/extrakey.yaml,'
            ' hbacsvcs/extrakey.yaml, hbacsvcs/invalidmember.yaml,'
            ' hostgroups/extrakey.yaml, hostgroups/invalidmember.yaml,'
            ' permissions/extrakey.yaml, privileges/extrakey.yaml,'
            ' privileges/invalidmember.yaml, roles/extrakey.yaml,'
            ' roles/invalidmember.yaml, services/extrakey.yaml,'
            ' services/invalidmember.yaml, sudorules/extrakey.yaml,'
            ' users/duplicit.yaml, users/duplicit2.yaml, users/extrakey.yaml,'
            ' users/invalidmember.yaml]')

# coding=utf-8

import logging
import mock
import pytest
import yaml
from testfixtures import LogCapture

from _utils import _import, _mock_dump
tool = _import('ipamanager', 'entities')
modulename = 'ipamanager.entities'

USER_GROUP_REGEX = r'^role-.+|.+-users$'


class TestFreeIPAEntity(object):
    def test_create_entity(self):
        with pytest.raises(TypeError) as exc:
            tool.FreeIPAEntity('sample.entity', {}, 'path')
        assert exc.value[0] == (
            "Can't instantiate abstract class FreeIPAEntity "
            "with abstract methods managed_attributes_push, validation_schema")

    def test_equality(self):
        user1 = tool.FreeIPAUser(
            'user1', {'firstName': 'Some', 'lastName': 'Name'}, 'path')
        user2 = tool.FreeIPAUser(
            'user1', {'firstName': 'Some', 'lastName': 'Name'}, 'path')
        assert user1 == user2
        user2.name = 'user2'
        assert user1 != user2

    def test_nonequality_different_type(self):
        group1 = tool.FreeIPAUserGroup('group', {}, 'path')
        group2 = tool.FreeIPAHostGroup('group', {}, 'path')
        assert group1 != group2

    def test_nonequality_same_type(self):
        rule1 = tool.FreeIPASudoRule('rule-one', {}, 'path')
        rule2 = tool.FreeIPASudoRule('rule-two', {}, 'path')
        assert rule1 != rule2
        rule2.name = 'rule-one'
        assert rule1 == rule2


class TestFreeIPAGroup(object):
    def test_create_group(self):
        with pytest.raises(TypeError) as exc:
            tool.FreeIPAGroup('sample-group', {}, 'path')
        assert exc.value[0] == (
            "Can't instantiate abstract class FreeIPAGroup "
            "with abstract methods allowed_members, validation_schema")


class TestFreeIPAHostGroup(object):
    def test_create_hostgroup_correct(self):
        data = {
            'description': 'Sample host group',
            'memberOf': {
                'hostgroup': ['group-one'],
                'hbacrule': ['rule-one'],
                'sudorule': ['rule-one']}}
        group = tool.FreeIPAHostGroup('group-one-hosts', data, 'path')
        assert group.name == 'group-one-hosts'
        assert group.data_repo == data
        assert group.data_ipa == {
            'description': ('Sample host group',),
            'memberof': {'hbacrule': ['rule-one'],
                         'hostgroup': ['group-one'],
                         'sudorule': ['rule-one']}}

    def test_create_hostgroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHostGroup(
                'group-one-hosts', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating group-one-hosts: "
            "extra keys not allowed @ data['extrakey']")


class TestFreeIPAUser(object):
    def test_create_user_correct(self):
        data = {
            'firstName': 'Some',
            'lastName': 'Name',
            'manager': 'sample.manager',
            'memberOf': {'group': ['group-one-users', 'group-two']}
        }
        user = tool.FreeIPAUser('archibald.jenkins', data, 'path')
        assert user.name == 'archibald.jenkins'
        assert user.data_repo == data
        assert user.data_ipa == {
            'givenname': ('Some',),
            'manager': ('sample.manager',),
            'memberof': {'group': ['group-one-users', 'group-two']},
            'sn': ('Name',)}

    def test_create_user_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUser(
                'archibald.jenkins', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating archibald.jenkins: "
            "extra keys not allowed @ data['extrakey']")

    def test_convert_to_ipa(self):
        data = {
            'firstName': 'Firstname',
            'lastName': 'Lastname',
            'initials': 'FL',
            'organizationUnit': 'TEST'
        }
        user = tool.FreeIPAUser('some.name', data, 'path')
        assert user._convert_to_ipa(data) == {
            'givenname': (u'Firstname',),
            'sn': (u'Lastname',),
            'initials': (u'FL',),
            'ou': (u'TEST',)
        }

    def test_convert_to_ipa_extended_latin(self):
        data = {
            'firstName': 'Firstname',
            'lastName': u'Laštname',
            'initials': 'FL',
            'organizationUnit': 'TEST'
        }
        user = tool.FreeIPAUser('some.name', data, 'path')
        assert user._convert_to_ipa(data) == {
            'givenname': (u'Firstname',), 'initials': (u'FL',),
            'ou': (u'TEST',), 'sn': (u'La\u0161tname',)}

    def test_convert_to_repo(self):
        data = {
            u'memberof_group': (
                u'ipausers', u'group-one-users',
                u'group-two', u'group-three-users'),
            u'cn': (u'Firstname Lastname',),
            u'krbcanonicalname': (u'firstname.lastname@DEVGDC.COM',),
            u'memberof_sudorule': (u'rule-one', u'rule-three', u'rule-two'),
            u'homedirectory': (u'/home/firstname.lastname',),
            u'nsaccountlock': False, u'uid': (u'firstname.lastname',),
            u'title': (u'Sr. SW Enginner',),
            u'loginshell': (u'/bin/sh',), u'uidnumber': (u'1916000053',),
            u'preserved': False,
            u'mail': (u'firstname.lastname@gooddata.com',),
            u'dn': u'uid=firstname.lastname,cn=users,cn=accounts,dc=test',
            u'displayname': (u'Firstname Lastname',),
            u'memberof_hbacrule': (u'rule-one', u'rule-three', u'rule-two'),
            u'carlicense': (u'github-account-one',),
            u'ipauniqueid': (u'b1204778-7c13-11e7-85dc-fa163e2e4384',),
            u'krbprincipalname': (u'firstname.lastname@DEVGDC.COM',),
            u'givenname': (u'Firstname',),
            u'objectclass': (
                u'ipaSshGroupOfPubKeys', u'ipaobject', u'mepOriginEntry',
                u'person', u'top', u'ipasshuser', u'inetorgperson',
                u'organizationalperson', u'krbticketpolicyaux',
                u'krbprincipalaux', u'inetuser', u'posixaccount'),
            u'gidnumber': (u'1916000053',),
            u'gecos': (u'Firstname Lastname',), u'sn': (u'Lastname',),
            u'ou': (u'CISTA',), u'initials': (u'FLA',)}
        user = tool.FreeIPAUser('firstname.lastname', {})
        result = user._convert_to_repo(data)
        assert result == {
            'initials': 'FLA',
            'title': 'Sr. SW Enginner',
            'firstName': 'Firstname',
            'lastName': 'Lastname',
            'emailAddress': 'firstname.lastname@gooddata.com',
            'githubLogin': 'github-account-one',
            'organizationUnit': 'CISTA'}
        assert all(isinstance(i, unicode) for i in result.itervalues())


class TestFreeIPAUserGroup(object):
    def test_create_usergroup_correct(self):
        data = {
            'description': 'Sample user group',
            'memberOf': {
                'group': ['group-one'],
                'hbacrule': ['rule-one'],
                'sudorule': ['rule-one']}}
        group = tool.FreeIPAUserGroup(
            'group-one-users', data, 'path')
        assert group.name == 'group-one-users'
        assert group.data_repo == data
        assert group.data_ipa == {
            'description': ('Sample user group',),
            'memberof': {'group': ['group-one'],
                         'hbacrule': ['rule-one'],
                         'sudorule': ['rule-one']}}
        assert isinstance(group.data_ipa['description'][0], unicode)

    def test_create_usergroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUserGroup(
                'group-one-users', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating group-one-users: "
            "extra keys not allowed @ data['extrakey']")

    def test_convert_to_repo(self):
        data = {
            u'dn': u'cn=group-three-users,cn=groups,cn=accounts,dc=test',
            u'cn': (u'group-three-users',),
            u'objectclass': (u'ipaobject', u'top', u'ipausergroup',
                             u'posixgroup', u'groupofnames', u'nestedgroup'),
            u'memberindirect_group': (u'group-one-users',),
            u'gidnumber': (u'1916000050',),
            u'ipauniqueid': (u'b0f9a352-7c13-11e7-99a4-fa163e2e4384',),
            u'member_group': (u'group-two',),
            u'member_user': (u'firstname.lastname2',),
            u'memberindirect_user': (u'kristian.lesko', u'firstname.lastname'),
            u'description': (u'Sample group three.',)}
        group = tool.FreeIPAUserGroup('group-three-users', {})
        result = group._convert_to_repo(data)
        assert result == {'description': 'Sample group three.'}
        assert isinstance(result['description'], unicode)

    def test_can_contain_users_yes(self):
        group = tool.FreeIPAUserGroup('group-one-users', {}, 'path')
        assert group.can_contain_users(USER_GROUP_REGEX)

    def test_can_contain_users_no(self):
        group = tool.FreeIPAUserGroup('group-one', {}, 'path')
        assert not group.can_contain_users(USER_GROUP_REGEX)

    def test_can_contain_users_yes_not_enforced(self):
        group = tool.FreeIPAUserGroup('group-one-users', {}, 'path')
        assert group.can_contain_users(pattern=None)

    def test_can_contain_users_no_not_enforced(self):
        group = tool.FreeIPAUserGroup('group-one', {}, 'path')
        assert group.can_contain_users(pattern=None)

    def test_cannot_contain_users_yes(self):
        group = tool.FreeIPAUserGroup('group-one', {}, 'path')
        assert group.cannot_contain_users(USER_GROUP_REGEX)

    def test_cannot_contain_users_no(self):
        group = tool.FreeIPAUserGroup('role-group-one', {}, 'path')
        assert not group.cannot_contain_users(USER_GROUP_REGEX)

    def test_cannot_contain_users_yes_not_enforced(self):
        group = tool.FreeIPAUserGroup('group-one-users', {}, 'path')
        assert group.cannot_contain_users(pattern=None)

    def test_cannot_contain_users_no_not_enforced(self):
        group = tool.FreeIPAUserGroup('group-one', {}, 'path')
        assert group.cannot_contain_users(pattern=None)

    def test_write_to_file(self):
        output = dict()
        group = tool.FreeIPAUserGroup(
            'group-three-users', {
                'description': 'Sample group three.',
                'memberOf': {'group': ['group-two']}}, 'some/path')
        with mock.patch('yaml.dump', _mock_dump(output, yaml.dump)):
            with mock.patch('__builtin__.open'):
                group.write_to_file()
        assert output == {
            'group-three-users': (
                '---\n'
                'group-three-users:\n'
                '  description: Sample group three.\n'
                '  memberOf:\n'
                '    group:\n'
                '      - group-two\n')}

    def test_write_to_file_no_path(self):
        group = tool.FreeIPAUserGroup(
            'group-three-users', {
                'description': 'Sample group three.',
                'memberOf': {'group': ['group-two']}}, 'some/path')
        group.path = None
        with pytest.raises(tool.ManagerError) as exc:
            group.write_to_file()
        assert exc.value[0] == (
            'group group-three-users has no file path, nowhere to write.')

    def test_write_to_file_error(self):
        group = tool.FreeIPAUserGroup(
            'group-three-users', {
                'description': 'Sample group three.',
                'memberOf': {'group': ['group-two']}}, 'some/path')
        with mock.patch('__builtin__.open') as mock_open:
            mock_open.side_effect = OSError('[Errno 13] Permission denied')
            with pytest.raises(tool.ConfigError) as exc:
                group.write_to_file()
        assert exc.value[0] == (
            'Cannot write group group-three-users '
            'to some/path: [Errno 13] Permission denied')

    def test_delete_file(self):
        group = tool.FreeIPAUserGroup(
            'group-three-users', {
                'description': 'Sample group three.',
                'memberOf': {'group': ['group-two']}}, 'some/path')
        with LogCapture('FreeIPAUserGroup', level=logging.DEBUG) as log:
            with mock.patch('%s.os.unlink' % modulename) as mock_unlink:
                group.delete_file()
                mock_unlink.assert_called_with('some/path')
        log.check(('FreeIPAUserGroup', 'DEBUG',
                   'group-three-users config file deleted'))

    def test_delete_file_no_path(self):
        group = tool.FreeIPAUserGroup(
            'group-three-users', {
                'description': 'Sample group three.',
                'memberOf': {'group': ['group-two']}}, 'path')
        group.path = None
        with pytest.raises(tool.ManagerError) as exc:
            group.delete_file()
        assert exc.value[0] == (
            'group group-three-users has no file path, cannot delete.')

    def test_delete_file_error(self):
        group = tool.FreeIPAUserGroup(
            'group-three-users', {
                'description': 'Sample group three.',
                'memberOf': {'group': ['group-two']}})
        group.path = 'some/path'
        with mock.patch('%s.os.unlink' % modulename) as mock_unlink:
            mock_unlink.side_effect = OSError('[Errno 13] Permission denied')
            with pytest.raises(tool.ConfigError) as exc:
                group.delete_file()
        mock_unlink.assert_called_with('some/path')
        assert exc.value[0] == (
            'Cannot delete group group-three-users '
            'at some/path: [Errno 13] Permission denied')


class TestFreeIPAHBACRule(object):
    def test_create_hbac_rule_correct(self):
        rule = tool.FreeIPAHBACRule(
            'rule-one', {'description': 'Sample HBAC rule'}, 'path')
        assert rule.name == 'rule-one'
        assert rule.data_repo == {'description': 'Sample HBAC rule'}
        assert rule.data_ipa == {'description': ('Sample HBAC rule',)}

    def test_create_hbac_rule_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHBACRule('rule-one', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating rule-one: extra keys "
            "not allowed @ data['extrakey']")

    def test_convert_to_ipa(self):
        data = {
            'description': 'A sample sudo rule.',
            'memberHost': ['hosts-one'],
            'memberUser': ['users-one']
        }
        user = tool.FreeIPAHBACRule('rule-one', data, 'path')
        assert user._convert_to_ipa(data) == {
            'description': ('A sample sudo rule.',),
            'memberhost': ('hosts-one',),
            'memberuser': ('users-one',)
        }

    def test_create_commands_member_same(self):
        rule = tool.FreeIPAHBACRule('rule-one', {'memberHost': ['group-one'],
                                    'memberUser': ['group-one']}, 'path')
        remote_rule = tool.FreeIPAHBACRule('rule-one', {
            'cn': ('rule-one',), 'memberuser_group': ('group-one',),
            'memberhost_hostgroup': ('group-one',)})
        assert not rule.create_commands(remote_rule)

    def test_create_commands_member_add(self):
        rule = tool.FreeIPAHBACRule('rule-one', {'memberHost': ['group-one'],
                                    'memberUser': ['group-one']}, 'path')
        remote_rule = tool.FreeIPAHBACRule('rule-one', {'cn': ('rule-one',)})
        commands = rule.create_commands(remote_rule)
        assert len(commands) == 2
        assert [i.command for i in commands] == [
            'hbacrule_add_host', 'hbacrule_add_user']
        assert [i.description for i in commands] == [
            u'hbacrule_add_host rule-one (hostgroup=group-one)',
            u'hbacrule_add_user rule-one (group=group-one)']
        assert [i.payload for i in commands] == [
            {'cn': u'rule-one', 'hostgroup': u'group-one'},
            {'cn': u'rule-one', 'group': u'group-one'}]

    def test_create_commands_member_remove(self):
        rule = tool.FreeIPAHBACRule('rule-one', {'memberHost': ['group-one'],
                                    'memberUser': ['group-one']}, 'path')
        rule.data_repo = dict()  # rule must have members when created
        rule.data_ipa = dict()  # rule must have members when created
        remote_rule = tool.FreeIPAHBACRule(
            'rule-one', {
                'cn': ('rule-one',), 'memberuser_group': ('group-one',),
                'memberhost_hostgroup': ('group-one',)})
        commands = rule.create_commands(remote_rule)
        assert len(commands) == 2
        assert [i.command for i in commands] == [
            'hbacrule_remove_host', 'hbacrule_remove_user']
        assert [i.description for i in commands] == [
            u'hbacrule_remove_host rule-one (hostgroup=group-one)',
            u'hbacrule_remove_user rule-one (group=group-one)']
        assert [i.payload for i in commands] == [
            {'cn': u'rule-one', 'hostgroup': u'group-one'},
            {'cn': u'rule-one', 'group': u'group-one'}]


class TestFreeIPASudoRule(object):
    def setup_method(self, method):
        self.ipa_data = {
            u'dn': u'ipaUniqueID=d3086a54-7b60-11e7-947e-fa163e2e4384,cn=test',
            u'cn': (u'rule-one',),
            u'objectclass': (u'ipasudorule', u'ipaassociation'),
            u'memberhost_hostgroup': (u'group-two',),
            u'memberuser_group': (u'group-two',),
            u'ipauniqueid': (u'd3086a54-7b60-11e7-947e-fa163e2e4384',),
            u'ipaenabledflag': (u'TRUE',),
            u'ipasudoopt': (u'!authenticate',),
            u'description': (u'Sample sudo rule one',)}

    def test_create_sudo_rule_repo_correct(self):
        rule = tool.FreeIPASudoRule(
            'rule-one', {'description': 'Sample sudo rule'}, 'path')
        assert rule.name == 'rule-one'
        assert rule.data_repo == {'description': 'Sample sudo rule'}
        assert rule.data_ipa == {'description': ('Sample sudo rule',)}

    def test_create_sudo_rule_repo_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPASudoRule('rule-one', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating rule-one: "
            "extra keys not allowed @ data['extrakey']")

    def test_create_sudo_rule_ipa(self):
        rule = tool.FreeIPASudoRule(u'rule-one', self.ipa_data)
        assert rule.name == 'rule-one'
        assert rule.data_repo == {'description': 'Sample sudo rule one',
                                  'options': ['!authenticate']}
        assert isinstance(rule.data_repo['description'], unicode)
        assert isinstance(rule.data_repo['options'][0], unicode)
        assert rule.data_ipa == self.ipa_data

    def test_create_commands_option_add(self):
        rule = tool.FreeIPASudoRule(
            'rule-one', {'options': ['!test', '!test2']}, 'path')
        remote_rule = tool.FreeIPASudoRule('rule-one', {'cn': (u'rule-one',)})
        commands = rule.create_commands(remote_rule)
        assert len(commands) == 2
        assert all(i.command == 'sudorule_add_option' for i in commands)
        assert sorted([(i.description, i.payload) for i in commands]) == [
            (u'sudorule_add_option rule-one (ipasudoopt=!test)',
             {'cn': u'rule-one', 'ipasudoopt': u'!test'}),
            (u'sudorule_add_option rule-one (ipasudoopt=!test2)',
             {'cn': u'rule-one', 'ipasudoopt': u'!test2'})]

    def test_create_commands_option_remove(self):
        rule = tool.FreeIPASudoRule('rule-one', {'options': ['!test']}, 'path')
        remote_rule = tool.FreeIPASudoRule(
            'rule-one', {'cn': (u'rule-one',),
                         'ipasudoopt': (u'!test', u'!test2')})
        commands = rule.create_commands(remote_rule)
        assert len(commands) == 1
        assert commands[0].command == 'sudorule_remove_option'
        assert commands[0].description == (
            'sudorule_remove_option rule-one (ipasudoopt=!test2)')
        assert commands[0].payload == {
            'cn': u'rule-one', 'ipasudoopt': u'!test2'}

    def test_convert_to_repo(self):
        rule = tool.FreeIPASudoRule('rule-one', {})
        result = rule._convert_to_repo(self.ipa_data)
        assert result == {
            'description': 'Sample sudo rule one',
            'options': ['!authenticate']}
        assert isinstance(result['description'], unicode)
        assert isinstance(result['options'][0], unicode)

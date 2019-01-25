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


class TestFreeIPAPrivilege(object):
    def test_create_privilege(self):
        data = {
            'description': 'Sample privilege',
            'memberOf': {
                'permission': ['permission-one']}
        }
        privilege = tool.FreeIPAPrivilege('privilege-one', data, 'path')
        assert privilege.name == 'privilege-one'
        assert privilege.data_repo == data
        assert privilege.data_ipa == {
            'description': ('Sample privilege',),
            'memberof': {'permission': ['permission-one']}
        }

    def test_create_privilege_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAPrivilege(
                'privilege-one', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating privilege-one: "
            "extra keys not allowed @ data['extrakey']")

    def test_convert_to_ipa(self):
        data = {
            'description': 'Good description',
        }
        privilege = tool.FreeIPAPrivilege('privilege-one', data, 'path')
        assert privilege._convert_to_ipa(data) == {
            'description': (u'Good description',)}

    def test_convert_to_repo(self):
        data = {
            u'objectclass': (u'top', u'groupofnames', u'nestedgroup'),
            u'dn': (u'cn=Write IPA Configuration,cn=privileges'
                    u',cn=pbac,dc=devgdc,dc=com'),
            u'memberof_permission': (u'Write IPA Configuration',),
            u'cn': (u'Write IPA Configuration',),
            u'description': (u'Write IPA Configuration',)
        }
        privilege = tool.FreeIPAPrivilege('role-one', {})
        result = privilege._convert_to_repo(data)
        assert result == {'description': u'Write IPA Configuration'}
        assert all(isinstance(i, unicode) for i in result.itervalues())


class TestFreeIPAHostGroup(object):
    def test_create_hostgroup_correct(self):
        data = {
            'description': 'Sample host group',
            'memberOf': {
                'hostgroup': ['group-one'],
                'hbacrule': ['rule-one'],
                'sudorule': ['rule-one'],
                'role': ['role-one']}}
        group = tool.FreeIPAHostGroup('group-one-hosts', data, 'path')
        assert group.name == 'group-one-hosts'
        assert group.data_repo == data
        assert group.data_ipa == {
            'description': ('Sample host group',),
            'memberof': {'hbacrule': ['rule-one'],
                         'hostgroup': ['group-one'],
                         'sudorule': ['rule-one'],
                         'role': ['role-one']}}

    def test_create_hostgroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHostGroup(
                'group-one-hosts', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating group-one-hosts: "
            "extra keys not allowed @ data['extrakey']")


class TestFreeIPAPermission(object):
    data = {
        'description': 'Simple description',
        'subtree': 'Here is subtree',
        'attributes': ['nice attributes', 'some more attrs'],
        'location': 'This is my location',
        'grantedRights': 'some rigths',
        'defaultAttr': 'default attributes'}

    def test_create_permission_correct(self):
        permission = tool.FreeIPAPermission(
            'sample-permission', self.data, 'path')
        assert permission.name == 'sample-permission'
        assert permission.data_repo == self.data
        assert permission.data_ipa == {
            'description': ('Simple description',),
            'attrs': ('nice attributes', 'some more attrs'),
            'ipapermdefaultattr': ('default attributes',),
            'ipapermlocation': ('This is my location',),
            'ipapermright': ('some rigths',),
            'subtree': ('Here is subtree',)
        }

    def test_permission_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPARole(
                'sample_permission', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating sample_permission: "
            "extra keys not allowed @ data['extrakey']")

    def test_convert_to_ipa(self):
        permission = tool.FreeIPAPermission(
            'permission-one', self.data, 'path')
        assert permission._convert_to_ipa(self.data) == {
            'attrs': (u'nice attributes', u'some more attrs'),
            'description': (u'Simple description',),
            'ipapermdefaultattr': (u'default attributes',),
            'ipapermlocation': (u'This is my location',),
            'ipapermright': (u'some rigths',),
            'subtree': (u'Here is subtree',)}

    def test_convert_to_repo(self):
        data = {
            u'ipapermright': (u'write',),
            u'dn': (u'cn=Request Certificate,cn=permissions'
                    u',cn=pbac,dc=devgdc,dc=com'),
            u'ipapermbindruletype': (u'permission',),
            u'cn': (u'Request Certificate',),
            u'objectclass': (u'top', u'groupofnames', u'ipapermission'),
            u'member_privilege': (u'Certificate Administrators',),
            u'ipapermtarget': ((u'cn=request certificate,cn=virtual operations'
                                u',cn=etc,dc=devgdc,dc=com',)),
            u'attrs': (u'objectclass',),
            u'ipapermlocation': (u'dc=devgdc,dc=com',),
            u'ipapermincludedattr': (u'objectclass',)}
        permission = tool.FreeIPAPermission('permission-one', {})
        result = permission._convert_to_repo(data)
        assert result == {
            'attributes': u'objectclass',
            'grantedRights': u'write',
            'location': u'dc=devgdc,dc=com'}
        assert all(isinstance(i, unicode) for i in result.itervalues())


class TestFreeIPARole(object):
    def test_create_role_correct(self):
        data = {
            'description': 'Some description',
            'memberOf': {'privilege': [
                'privilege_simple', 'another_privilege']}}
        role = tool.FreeIPARole('sample_role', data, 'path')
        assert role.name == 'sample_role'
        assert role.data_repo == data
        assert role.data_ipa == {
            'description': ('Some description', ),
            'memberof': {'privilege': [
                'privilege_simple', 'another_privilege']}}

    def test_create_role_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPARole(
                'sample_role', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating sample_role: "
            "extra keys not allowed @ data['extrakey']")

    def test_convert_to_ipa(self):
        data = {
            'description': 'Good description',
        }
        role = tool.FreeIPARole('some.name', data, 'path')
        assert role._convert_to_ipa(data) == {
            'description': (u'Good description',)}

    def test_convert_to_repo(self):
        data = {
            u'objectclass': (u'groupofnames', u'nestedgroup', u'top'),
            u'dn': u'cn=Test IPA Role,cn=roles,cn=accounts,dc=devgdc,dc=com',
            u'cn': (u'Test IPA Role',),
            u'description': (u'Here is some beautiful description',)}
        role = tool.FreeIPARole('role-one', {})
        result = role._convert_to_repo(data)
        assert result == {'description': u'Here is some beautiful description'}
        assert all(isinstance(i, unicode) for i in result.itervalues())


class TestFreeIPAHBACService(object):
    def test_create_hbacsvc_correct(self):
        data = {
            'description': 'Some description',
            'memberOf': {'hbacsvcgroup': [
                'simple_hbacsvcgroup', 'another_hbacsvcgroup']}
        }
        hbacsvc = tool.FreeIPAHBACService('sample_hbacsvc', data, 'path')
        assert hbacsvc.name == 'sample_hbacsvc'
        assert hbacsvc.data_repo == data
        assert hbacsvc.data_ipa == {
            'description': ('Some description', ),
            'memberof': {'hbacsvcgroup': [
                'simple_hbacsvcgroup', 'another_hbacsvcgroup']}}

    def test_create_hbacsvc_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHBACService(
                'sample_hbacsvc', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating sample_hbacsvc: "
            "extra keys not allowed @ data['extrakey']")

    def test_convert_to_ipa(self):
        data = {
            'description': 'Good description',
        }
        hbacsvc = tool.FreeIPAHBACService('some.name', data, 'path')
        assert hbacsvc._convert_to_ipa(data) == {
            'description': (u'Good description',)}

    def test_convert_to_repo(self):
        data = {
            u'dn': u'cn=proftpd,cn=hbacservices,cn=hbac,dc=devgdc,dc=com',
            u'memberof_hbacsvcgroup': (u'ftp',), u'description': (u'proftpd',),
            u'objectclass': (u'ipahbacservice', u'ipaobject'), u'ipauniqueid':
            (u'a3bebe26-84ea-11e8-b8dc-fa163e198b8c',), u'cn': (u'proftpd',)}
        hbacsvc = tool.FreeIPAHBACService('role-one', {})
        result = hbacsvc._convert_to_repo(data)
        assert result == {'description': u'proftpd'}
        assert all(isinstance(i, unicode) for i in result.itervalues())


class TestFreeIPAHBACServiceGroup(object):
    def test_create_hbacsvcgroup_correct(self):
        data = {
            'description': 'Some description',
        }
        hbacsvcgroup = tool.FreeIPAHBACServiceGroup(
            'sample_hbacsvcgroup', data, 'path')
        assert hbacsvcgroup.name == 'sample_hbacsvcgroup'
        assert hbacsvcgroup.data_repo == data
        assert hbacsvcgroup.data_ipa == {
            'description': ('Some description', )}

    def test_create_hbacsvcgroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAHBACServiceGroup(
                'sample_hbacsvcgroup', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating sample_hbacsvcgroup: "
            "extra keys not allowed @ data['extrakey']")

    def test_convert_to_ipa(self):
        data = {
            'description': 'Good description',
        }
        hbacsvcgroup = tool.FreeIPAHBACServiceGroup('some.name', data, 'path')
        assert hbacsvcgroup._convert_to_ipa(data) == {
            'description': (u'Good description',)}

    def test_convert_to_repo(self):
        data = {
            u'dn': u'cn=Sudo,cn=hbacservicegroups,cn=hbac,dc=devgdc,dc=com',
            u'cn': (u'Sudo',),
            u'objectclass': (u'ipaobject', u'ipahbacservicegroup',
                             u'nestedGroup', u'groupOfNames', u'top'),
            u'member_hbacsvc': (u'sudo', u'sudo-i', u'vsftpd'),
            u'ipauniqueid': (u'06257a7e-84ea-11e8-9f84-fa163e198b8c',),
            u'description': (u'Default group of Sudo related services',)}
        hbacsvcgroup = tool.FreeIPAHBACService('role-one', {})
        result = hbacsvcgroup._convert_to_repo(data)
        assert result == {
            'description': u'Default group of Sudo related services'}
        assert all(isinstance(i, unicode) for i in result.itervalues())


class TestFreeIPAService(object):
    def test_create_service_correct(self):
        data = {
            'description': 'Some description',
            'memberOf': {'role': ['role_simple', 'another_role']},
            'managedBy': 'Host'
        }
        service = tool.FreeIPAService('sample_service', data, 'path')
        assert service.name == 'sample_service'
        assert service.data_repo == data
        assert service.data_ipa == {
            'description': ('Some description', ),
            'memberof': {'role': ['role_simple', 'another_role']},
            'managedby_host': ('Host',)}

    def test_create_service_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAService(
                'sample_service', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating sample_service: "
            "extra keys not allowed @ data['extrakey']")

    def test_change_path(self):
        output = dict()
        data = {
            'description': 'Some description',
            'memberOf': {'role': ['role_simple', 'another_role']},
            'managedBy': 'Host'
        }
        service = tool.FreeIPAService(
            'sample_service', data,
            'some/path/to/ldap/ipa01.devgdc.com@DEVGDC.COM')
        with mock.patch('yaml.dump', _mock_dump(output, yaml.dump)):
            with mock.patch('__builtin__.open'):
                service.write_to_file()
        assert service.path == 'some/path/to/ldap-ipa01_devgdc_com.yaml'

    def test_convert_to_ipa(self):
        data = {
            'description': 'Good description',
            'managedBy': 'some@host.name.com',
        }
        service = tool.FreeIPAService('service-one', data, 'path')
        assert service._convert_to_ipa(data) == {
            'description': (u'Good description',),
            'managedby_host': (u'some@host.name.com',)}

    def test_convert_to_repo(self):
        data = {
            u'ipakrbprincipalalias': (u'DNS/ipa01.devgdc.com@DEVGDC.COM',),
            u'krbextradata': ('\x00\x024\xa2j[host/admin@DEVGDC.COM\x00',),
            u'krbcanonicalname': (u'DNS/ipa01.devgdc.com@DEVGDC.COM',),
            u'ipakrbokasdelegate': False,
            u'ipauniqueid': (u'932370a0-9ae0-11e8-ad25-fa163ef99b4f',),
            u'krbpwdpolicyreference': (
                (u'cn=Default Service Password Policy,cn=services'
                 u',cn=accounts,dc=devgdc,dc=com',)),
            u'ipakrboktoauthasdelegate': False,
            u'krbprincipalname': (u'DNS/ipa01.devgdc.com@DEVGDC.COM',),
            u'managedby_host': (u'ipa01.devgdc.com',),
            u'description': (u'Some description',)}
        service = tool.FreeIPAService('service-one', {})
        result = service._convert_to_repo(data)
        assert result == {'description': u'Some description',
                          'managedBy': u'ipa01.devgdc.com'}
        assert all(isinstance(i, unicode) for i in result.itervalues())


class TestFreeIPAUser(object):
    def test_create_user_correct(self):
        data = {
            'firstName': 'Some',
            'lastName': 'Name',
            'manager': 'sample.manager',
            'memberOf': {
                        'group': ['group-one-users', 'group-two'],
                        'role': ['role-one-users', 'role-two']}
        }
        user = tool.FreeIPAUser('archibald.jenkins', data, 'path')
        assert user.name == 'archibald.jenkins'
        assert user.data_repo == data
        assert user.data_ipa == {
            'givenname': ('Some',),
            'manager': ('sample.manager',),
            'memberof': {
                'group': ['group-one-users', 'group-two'],
                'role': ['role-one-users', 'role-two']},
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
    def setup_method(self, method):
        self.data = {
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

    def test_create_usergroup_correct(self):
        data = {
            'description': 'Sample user group',
            'memberOf': {
                'group': ['group-one'],
                'hbacrule': ['rule-one'],
                'sudorule': ['rule-one'],
                'role': ['role-one']}}
        group = tool.FreeIPAUserGroup(
            'group-one-users', data, 'path')
        assert group.name == 'group-one-users'
        assert group.data_repo == data
        assert group.metaparams == {}
        assert group.data_ipa == {
            'description': ('Sample user group',),
            'memberof': {'group': ['group-one'],
                         'hbacrule': ['rule-one'],
                         'sudorule': ['rule-one'],
                         'role': ['role-one']}}
        assert isinstance(group.data_ipa['description'][0], unicode)
        assert group.posix

    def test_create_usergroup_correct_metaparams(self):
        data = {
            'description': 'Sample user group',
            'metaparams': {'someparam': 'testvalue'}}
        group = tool.FreeIPAUserGroup(
            'group-one-users', data, 'path')
        assert group.data_repo == {'description': 'Sample user group'}
        assert group.metaparams == {'someparam': 'testvalue'}

    def test_create_usergroup_correct_nonposix(self):
        data = {'description': 'Sample user group', 'posix': False}
        group = tool.FreeIPAUserGroup(
            'group-one-users', data, 'path')
        assert group.data_repo == {
            'description': 'Sample user group', 'posix': False}
        assert group.metaparams == {}
        assert not group.posix

    def test_create_usergroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            tool.FreeIPAUserGroup(
                'group-one-users', {'extrakey': 'bad'}, 'path')
        assert exc.value[0] == (
            "Error validating group-one-users: "
            "extra keys not allowed @ data['extrakey']")

    def test_create_usergroup_ipa_posix(self):
        group = tool.FreeIPAUserGroup('group-three-users', self.data)
        assert group.name == 'group-three-users'
        assert group.data_ipa == self.data
        assert group.data_repo == {
            'description': 'Sample group three.', 'posix': True}
        assert group.posix

    def test_create_usergroup_ipa_nonposix(self):
        self.data[u'objectclass'] = (u'ipaobject', u'top', u'ipausergroup',
                                     u'groupofnames', u'nestedgroup'),
        group = tool.FreeIPAUserGroup('group-three-users', self.data)
        assert group.name == 'group-three-users'
        assert group.data_ipa == self.data
        assert group.data_repo == {
            'description': 'Sample group three.', 'posix': False}
        assert not group.posix

    def test_convert_to_repo(self):
        result = tool.FreeIPAUserGroup('group', {})._convert_to_repo(self.data)
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

    def test_write_to_file_nonposix(self):
        output = dict()
        group = tool.FreeIPAUserGroup(
            'group-one', {'description': 'Sample group',
                          'metaparams': {'nonposix': True}}, 'path')
        with mock.patch('yaml.dump', _mock_dump(output, yaml.dump)):
            with mock.patch('__builtin__.open'):
                group.write_to_file()
        assert output == {'group-one': '---\n'
                                       'group-one:\n'
                                       '  description: Sample group\n'
                                       '  metaparams:\n'
                                       '    nonposix: true\n'}

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
                   'group group-three-users config file deleted'))

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
                'memberOf': {'group': ['group-two']}}, 'some/path')
        with mock.patch('%s.os.unlink' % modulename) as mock_unlink:
            mock_unlink.side_effect = OSError('[Errno 13] Permission denied')
            with pytest.raises(tool.ConfigError) as exc:
                group.delete_file()
        mock_unlink.assert_called_with('some/path')
        assert exc.value[0] == (
            'Cannot delete group group-three-users '
            'at some/path: [Errno 13] Permission denied')

    def test_create_commands_same(self):
        group = tool.FreeIPAUserGroup(
            'group-one', {'description': 'Sample group'}, 'path')
        remote_group = tool.FreeIPAUserGroup('rule-one', {
            'cn': ('group-one',), 'description': (u'Sample group',),
            'objectclass': (u'posixgroup',)})
        assert not group.create_commands(remote_group)

    def test_create_commands_repo_posix(self):
        group = tool.FreeIPAUserGroup(
            'group-one', {'description': 'Sample group'}, 'path')
        remote_group = tool.FreeIPAUserGroup('rule-one', {
            'cn': ('group-one',), 'description': (u'Sample group',)})
        cmds = group.create_commands(remote_group)
        assert len(cmds) == 1
        assert cmds[0].command == 'group_mod'
        assert cmds[0].payload == {'cn': 'group-one', 'posix': True}
        assert cmds[0].description == 'group_mod group-one (make POSIX)'

    def test_create_commands_ipa_posix(self):
        group = tool.FreeIPAUserGroup('group-one', {'posix': False}, 'path')
        remote_group = tool.FreeIPAUserGroup('rule-one', {
            'cn': ('group-one',), 'objectclass': (u'posixgroup',)})
        cmds = group.create_commands(remote_group)
        assert len(cmds) == 1
        assert cmds[0].command == 'group_mod'
        assert cmds[0].payload == {'cn': u'group-one',
                                   'delattr': u'objectclass=posixgroup',
                                   'setattr': u'gidnumber='}
        assert cmds[0].description == 'group_mod group-one (make non-POSIX)'

    def test_create_commands_new_posix(self):
        group = tool.FreeIPAUserGroup(
            'group-one', {'description': 'Sample group'}, 'path')
        cmds = group.create_commands(None)
        assert len(cmds) == 1
        assert cmds[0].command == 'group_add'

    def test_create_commands_new_nonposix(self):
        group = tool.FreeIPAUserGroup('group-one', {'posix': False}, 'path')
        cmds = group.create_commands(None)
        assert len(cmds) == 1
        assert cmds[0].command == 'group_add'
        assert cmds[0].payload == {'cn': 'group-one', 'nonposix': True}
        assert cmds[0].description == 'group_add group-one (nonposix=True)'


class TestFreeIPAHBACRule(object):
    def test_create_hbac_rule_correct(self):
        rule = tool.FreeIPAHBACRule(
            'rule-one', {'description': 'Sample HBAC rule'}, 'path')
        assert rule.name == 'rule-one'
        assert rule.data_repo == {
            'description': 'Sample HBAC rule', 'serviceCategory': 'all'}
        assert rule.data_ipa == {
            'description': ('Sample HBAC rule',), 'servicecategory': (u'all',)}

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
            'description': (u'A sample sudo rule.',),
            'memberhost': (u'hosts-one',),
            'memberuser': (u'users-one',),
            'servicecategory': (u'all',)
        }

    def test_create_commands_member_same(self):
        rule = tool.FreeIPAHBACRule('rule-one', {'memberHost': ['group-one'],
                                    'memberUser': ['group-one']}, 'path')
        remote_rule = tool.FreeIPAHBACRule('rule-one', {
            'cn': ('rule-one',), 'memberuser_group': ('group-one',),
            'memberhost_hostgroup': ('group-one',),
            u'servicecategory': (u'all',)})
        assert not rule.create_commands(remote_rule)

    def test_create_commands_member_add(self):
        rule = tool.FreeIPAHBACRule('rule-one', {'memberHost': ['group-one'],
                                    'memberUser': ['group-one']}, 'path')
        remote_rule = tool.FreeIPAHBACRule(
            'rule-one', {u'cn': (u'rule-one',), u'servicecategory': (u'all',)})
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

    def test_write_to_file_no_default_attributes(self):
        rule = tool.FreeIPAHBACRule(
            'rule-one', {'description': 'Sample HBAC rule'}, 'path')
        rule.default_attributes = []
        assert rule.data_repo == {
            'description': 'Sample HBAC rule', 'serviceCategory': 'all'}
        output = dict()
        with mock.patch('yaml.dump', _mock_dump(output, yaml.dump)):
            with mock.patch('__builtin__.open'):
                rule.write_to_file()
        assert output == {'rule-one': '---\nrule-one:\n'
                                      '  description: Sample HBAC rule\n'
                                      '  serviceCategory: all\n'}

    def test_write_to_file_default_attributes(self):
        rule = tool.FreeIPAHBACRule(
            'rule-one', {'description': 'Sample HBAC rule'}, 'path')
        assert rule.data_repo == {
            'description': 'Sample HBAC rule', 'serviceCategory': 'all'}
        output = dict()
        with mock.patch('yaml.dump', _mock_dump(output, yaml.dump)):
            with mock.patch('__builtin__.open'):
                rule.write_to_file()
        assert output == {'rule-one': '---\nrule-one:\n'
                                      '  description: Sample HBAC rule\n'}


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
            u'ipasudoopt': (u'!authenticate', u'!requiretty'),
            u'description': (u'Sample sudo rule one',)}

    def test_create_sudo_rule_repo_correct(self):
        rule = tool.FreeIPASudoRule(
            'rule-one', {'description': 'Sample sudo rule'}, 'path')
        assert rule.name == 'rule-one'
        assert rule.data_repo == {
            'cmdCategory': 'all', 'description': 'Sample sudo rule',
            'options': ['!authenticate', '!requiretty'],
            'runAsGroupCategory': 'all', 'runAsUserCategory': 'all'}
        assert rule.data_ipa == {
            'cmdcategory': (u'all',), 'description': (u'Sample sudo rule',),
            'ipasudoopt': (u'!authenticate', u'!requiretty'),
            'ipasudorunasgroupcategory': (u'all',),
            'ipasudorunasusercategory': (u'all',)}

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
                                  'options': ['!authenticate', '!requiretty']}
        assert isinstance(rule.data_repo['description'], unicode)
        assert isinstance(rule.data_repo['options'][0], unicode)
        assert rule.data_ipa == self.ipa_data

    def test_create_commands_new(self):
        rule = tool.FreeIPASudoRule('rule-one', {}, 'path')
        commands = rule.create_commands(None)
        assert len(commands) == 3
        assert sorted([i.command for i in commands]) == [
            'sudorule_add', 'sudorule_add_option', 'sudorule_add_option']
        assert sorted([i.description for i in commands]) == [
            (u'sudorule_add rule-one (cmdcategory=all; '
             u'ipasudorunasgroupcategory=all; ipasudorunasusercategory=all)'),
            u'sudorule_add_option rule-one (ipasudoopt=!authenticate)',
            u'sudorule_add_option rule-one (ipasudoopt=!requiretty)']
        assert sorted([i.payload for i in commands]) == [
            {'cn': u'rule-one', 'ipasudoopt': u'!authenticate'},
            {'cn': u'rule-one', 'ipasudoopt': u'!requiretty'},
            {'cmdcategory': u'all', 'cn': u'rule-one',
             'ipasudorunasgroupcategory': u'all',
             'ipasudorunasusercategory': u'all'}]

    def test_create_commands_option_add(self):
        rule = tool.FreeIPASudoRule('rule-one', {}, 'path')
        remote_rule = tool.FreeIPASudoRule(
            'rule-one', {'cn': (u'rule-one',), 'cmdcategory': (u'all',),
                         'ipasudorunasgroupcategory': (u'all',),
                         'ipasudorunasusercategory': (u'all',)})
        commands = rule.create_commands(remote_rule)
        assert len(commands) == 2
        assert all(i.command == 'sudorule_add_option' for i in commands)
        assert sorted([(i.description, i.payload) for i in commands]) == [
            (u'sudorule_add_option rule-one (ipasudoopt=!authenticate)',
             {'cn': u'rule-one', 'ipasudoopt': u'!authenticate'}),
            (u'sudorule_add_option rule-one (ipasudoopt=!requiretty)',
             {'cn': u'rule-one', 'ipasudoopt': u'!requiretty'})]

    def test_create_commands_option_remove(self):
        rule = tool.FreeIPASudoRule('rule-one', {}, 'path')
        remote_rule = tool.FreeIPASudoRule(
            'rule-one', {'cn': (u'rule-one',),
                         'ipasudoopt': (u'!test', u'!test2')})
        commands = rule.create_commands(remote_rule)
        assert len(commands) == 5
        assert sorted([i.command for i in commands]) == [
            'sudorule_add_option', 'sudorule_add_option', 'sudorule_mod',
            'sudorule_remove_option', 'sudorule_remove_option']
        assert sorted([i.description for i in commands]) == [
            u'sudorule_add_option rule-one (ipasudoopt=!authenticate)',
            u'sudorule_add_option rule-one (ipasudoopt=!requiretty)',
            (u'sudorule_mod rule-one (cmdcategory=all; '
             u'ipasudorunasgroupcategory=all; ipasudorunasusercategory=all)'),
            u'sudorule_remove_option rule-one (ipasudoopt=!test)',
            u'sudorule_remove_option rule-one (ipasudoopt=!test2)']
        assert sorted([i.payload for i in commands]) == [
            {'cn': u'rule-one', 'ipasudoopt': u'!authenticate'},
            {'cn': u'rule-one', 'ipasudoopt': u'!requiretty'},
            {'cn': u'rule-one', 'ipasudoopt': u'!test'},
            {'cn': u'rule-one', 'ipasudoopt': u'!test2'},
            {'cmdcategory': u'all', 'cn': u'rule-one',
             'ipasudorunasgroupcategory': u'all',
             'ipasudorunasusercategory': u'all'}]

    def test_convert_to_repo(self):
        rule = tool.FreeIPASudoRule('rule-one', {})
        result = rule._convert_to_repo(self.ipa_data)
        assert result == {
            'description': 'Sample sudo rule one',
            'options': ['!authenticate', '!requiretty']}
        assert isinstance(result['description'], unicode)
        assert isinstance(result['options'][0], unicode)

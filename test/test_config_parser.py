import os
import pytest
import sys
import yaml


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('config_parser')
entities = __import__('entities')
schemas = __import__('schemas')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')
CONFIG_INVALID = os.path.join(testpath, 'freeipa-manager-config/invalid')
USER_CORRECT = os.path.join(CONFIG_CORRECT, 'users/archibald_jenkins.yaml')
USER_CORRECT_SEVERAL = os.path.join(CONFIG_CORRECT, 'users/several.yaml')
USER_EXTRAKEY = os.path.join(CONFIG_INVALID, 'users/extrakey.yaml')
GROUP_CORRECT = os.path.join(CONFIG_CORRECT, '%sgroups/group_one.yaml')
GROUP_CORRECT_SEVERAL = os.path.join(CONFIG_CORRECT, '%sgroups/several.yaml')
GROUP_EXTRAKEY = os.path.join(CONFIG_INVALID, '%sgroups/extrakey.yaml')


class TestConfigParserBase(object):
    def load_conf(self, path, *args):
        with open(path % args, 'r') as src:
            return yaml.safe_load(src)


class TestConfigParser(TestConfigParserBase):
    def test_create_config_parser(self):
        with pytest.raises(TypeError) as exc:
            tool.ConfigParser()
        assert exc.value[0] == (
            "Can't instantiate abstract class ConfigParser "
            "with abstract methods entity_class, schema")

    def test_create_group_config_parser(self):
        with pytest.raises(TypeError) as exc:
            tool.GroupConfigParser()
        assert exc.value[0] == (
            "Can't instantiate abstract class GroupConfigParser "
            "with abstract methods entity_class")

    def test_create_host_group_config_parser(self):
        parser = tool.HostGroupConfigParser()
        assert parser.schema.schema == schemas.schema_groups
        assert parser.entity_class == entities.FreeIPAHostGroup

    def test_create_user_group_config_parser(self):
        parser = tool.UserGroupConfigParser()
        assert parser.schema.schema == schemas.schema_groups
        assert parser.entity_class == entities.FreeIPAUserGroup

    def test_create_user_config_parser(self):
        parser = tool.UserConfigParser()
        assert parser.schema.schema == schemas.schema_users
        assert parser.entity_class == entities.FreeIPAUser


class TestHostGroupConfigParser(TestConfigParserBase):
    def setup_method(self, method):
        self.parser = tool.UserGroupConfigParser()

    def test_parse_hostgroup_correct(self):
        parsed = self.parser.parse(self.load_conf(GROUP_CORRECT, 'host'))
        assert len(parsed) == 1
        group = parsed[0]
        assert isinstance(group, entities.FreeIPAUserGroup)
        assert group.name == 'group-one-hosts'
        assert group.dn == (
            'cn=group-one-hosts,cn=groups,cn=accounts,dc=intgdc,dc=com')
        assert group.data == {'description': ['Sample host group one']}

    def test_parse_hostgroup_correct_several(self):
        parsed = self.parser.parse(
            self.load_conf(GROUP_CORRECT_SEVERAL, 'host'))
        assert len(parsed) == 2
        assert all(isinstance(i, entities.FreeIPAUserGroup) for i in parsed)
        groups = sorted(parsed, key=lambda i: i.name)
        names = [group.name for group in groups]
        assert names == ['group-three-hosts', 'group-two']
        assert [group.dn for group in groups] == [
            'cn=group-three-hosts,cn=groups,cn=accounts,dc=intgdc,dc=com',
            'cn=group-two,cn=groups,cn=accounts,dc=intgdc,dc=com']
        data = [group.data for group in groups]
        assert data[0] == {
            'description': ['Sample host group three.'],
            'memberOf': [
                'cn=group-two,cn=hostgroups,cn=accounts,dc=intgdc,dc=com']
        }
        assert data[1] == {
            'description': ['Sample meta host group two.'],
            'memberOf': [
                'cn=group-one-hosts,cn=hostgroups,cn=accounts,dc=intgdc,dc=com'
            ]
        }

    def test_parse_hostgroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.parser.parse(self.load_conf(GROUP_EXTRAKEY, 'host'))
        assert (
            "extra keys not allowed @ data['group-one-hosts']['extrakey']"
            in str(exc)
        )


class TestUserConfigParser(TestConfigParserBase):
    def setup_method(self, method):
        self.parser = tool.UserConfigParser()
        self.group_dn = 'cn=groups,cn=accounts,dc=intgdc,dc=com'

    def test_parse_user_correct(self):
        data = self.load_conf(USER_CORRECT)
        parsed = self.parser.parse(data)
        assert len(parsed) == 1
        user = parsed[0]
        assert isinstance(user, entities.FreeIPAUser)
        assert user.name == 'archibald.jenkins'
        assert user.dn == (
            'uid=archibald.jenkins,cn=users,cn=accounts,dc=intgdc,dc=com')
        assert user.data == {
            'carLicense': ['yenkins'],
            'givenName': ['Archibald'],
            'mail': ['deli+jenkins@gooddata.com'],
            'ou': ['CISTA'],
            'sn': ['Jenkins'],
            'initials': ['AJE'],
            'manager': [
                'uid=sample.manager,cn=users,cn=accounts,dc=intgdc,dc=com'],
            'memberOf': [
                'cn=github-gooddata-hackers,%s' % self.group_dn,
                'cn=hipchat-users,%s' % self.group_dn,
                'cn=ipausers,%s' % self.group_dn,
                'cn=jenkins,%s' % self.group_dn,
                'cn=jira-gooddata-users,%s' % self.group_dn],
            'title': ['Sr. SW Enginner']
        }

    def test_parse_user_correct_several(self):
        data = self.load_conf(USER_CORRECT_SEVERAL)
        parsed = self.parser.parse(data)
        assert len(parsed) == 2
        assert all(isinstance(i, entities.FreeIPAUser) for i in parsed)
        users = sorted(parsed, key=lambda i: i.name)
        logins = [user.name for user in users]
        assert [user.dn for user in users] == [
            'uid=firstname.lastname,cn=users,cn=accounts,dc=intgdc,dc=com',
            'uid=firstname.lastname2,cn=users,cn=accounts,dc=intgdc,dc=com']
        assert logins == ['firstname.lastname', 'firstname.lastname2']
        user_data = [user.data for user in users]
        assert user_data[0] == {
            'carLicense': ['github-account-one'],
            'givenName': ['Firstname'],
            'initials': ['FLA'],
            'mail': ['firstname.lastname@gooddata.com'],
            'manager': [
                'uid=sample.manager,cn=users,cn=accounts,dc=intgdc,dc=com'],
            'memberOf': [
                'cn=github-gooddata-hackers,%s' % self.group_dn,
                'cn=hipchat-users,%s' % self.group_dn,
                'cn=ipausers,%s' % self.group_dn,
                'cn=jenkins,%s' % self.group_dn,
                'cn=jira-gooddata-users,%s' % self.group_dn],
            'ou': ['CISTA'],
            'sn': ['Lastname'],
            'title': ['Sr. SW Enginner']}
        assert user_data[1] == {
            'carLicense': ['github-account-two'],
            'givenName': ['Firstname'],
            'initials': ['FLN'],
            'mail': ['firstname.lastname2@gooddata.com'],
            'manager': [
                'uid=other.manager,cn=users,cn=accounts,dc=intgdc,dc=com'],
            'memberOf': [
                'cn=github-gooddata-hackers,%s' % self.group_dn,
                'cn=hipchat-users,%s' % self.group_dn,
                'cn=ipausers,%s' % self.group_dn,
                'cn=jenkins,%s' % self.group_dn,
                'cn=jira-gooddata-users,%s' % self.group_dn],
            'ou': ['CISTA'],
            'sn': ['Lastname'],
            'title': ['Sr. SW Enginner']}

    def test_parse_user_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.parser.parse(self.load_conf(USER_EXTRAKEY))
        assert (
            "extra keys not allowed @ data['extra.key']['invalid']" in str(exc)
        )

    def test_convert(self):
        data = {
            'firstName': 'Firstname',
            'lastName': 'Lastname',
            'initials': 'FL',
            'organizationUnit': 'TEST'
        }
        assert self.parser.convert(data) == {
            'givenName': ['Firstname'],
            'sn': ['Lastname'],
            'initials': ['FL'],
            'ou': ['TEST']
        }

    def test_map_memberof(self):
        assert self.parser._map_memberof({
            'usergroups': ['test-users']
        }) == ['cn=test-users,cn=groups,cn=accounts,dc=intgdc,dc=com']


class TestUserGroupConfigParser(TestConfigParserBase):
    def setup_method(self, method):
        self.parser = tool.UserGroupConfigParser()

    def test_parse_usergroup_correct(self):
        parsed = self.parser.parse(self.load_conf(GROUP_CORRECT, 'user'))
        assert len(parsed) == 1
        group = parsed[0]
        assert isinstance(group, entities.FreeIPAUserGroup)
        assert group.name == 'group-one-users'
        assert group.dn == (
            'cn=group-one-users,cn=groups,cn=accounts,dc=intgdc,dc=com')
        assert group.data == {
            'description': ['Sample group one']
        }

    def test_parse_usergroup_correct_several(self):
        parsed = self.parser.parse(
            self.load_conf(GROUP_CORRECT_SEVERAL, 'user'))
        assert len(parsed) == 2
        assert all(isinstance(i, entities.FreeIPAUserGroup) for i in parsed)
        groups = sorted(parsed, key=lambda i: i.name)
        names = [group.name for group in groups]
        assert names == ['group-three-users', 'group-two']
        assert [group.dn for group in groups] == [
            'cn=group-three-users,cn=groups,cn=accounts,dc=intgdc,dc=com',
            'cn=group-two,cn=groups,cn=accounts,dc=intgdc,dc=com']
        data = [group.data for group in groups]
        assert data[0] == {
            'description': ['Sample group three.'],
            'memberOf': ['cn=group-two,cn=groups,cn=accounts,dc=intgdc,dc=com']
        }
        assert data[1] == {
            'description': ['Sample meta group two.'],
            'memberOf': [
                'cn=group-one-users,cn=groups,cn=accounts,dc=intgdc,dc=com']
        }

    def test_parse_usergroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.parser.parse(self.load_conf(GROUP_EXTRAKEY, 'user'))
        assert (
            "extra keys not allowed @ data['group-one-users']['extrakey']"
            in str(exc)
        )

    def test_convert(self):
        data = {
            'description': 'A sample group.',
            'memberOf': {'usergroups': ['group-one']}
        }
        assert self.parser.convert(data) == {
            'description': ['A sample group.'],
            'memberOf': [
                'cn=group-one,cn=groups,cn=accounts,dc=intgdc,dc=com']}

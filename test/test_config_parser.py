import os
import pytest
import sys
import yaml


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('config_parser')
entities = __import__('entities')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')
CONFIG_INVALID = os.path.join(testpath, 'freeipa-manager-config/invalid')
USER_CORRECT = os.path.join(CONFIG_CORRECT, 'users/archibald_jenkins.yaml')
USER_CORRECT_SEVERAL = os.path.join(CONFIG_CORRECT, 'users/several.yaml')
USER_MISSINGKEY = os.path.join(CONFIG_INVALID, 'users/missingkey.yaml')
USER_EXTRAKEY = os.path.join(CONFIG_INVALID, 'users/extrakey.yaml')
GROUP_CORRECT = os.path.join(CONFIG_CORRECT, '%sgroups/group_one.yaml')
GROUP_CORRECT_SEVERAL = os.path.join(CONFIG_CORRECT, '%sgroups/several.yaml')
GROUP_MISSINGKEY = os.path.join(CONFIG_INVALID, '%sgroups/missingkey.yaml')
GROUP_EXTRAKEY = os.path.join(CONFIG_INVALID, '%sgroups/extrakey.yaml')


class TestConfigParser(object):
    def load_conf(self, path, *args):
        with open(path % args, 'r') as src:
            return yaml.safe_load(src)


class TestHostGroupConfigParser(TestConfigParser):
    def setup_method(self, method):
        self.parser = tool.UserGroupConfigParser()

    def test_parse_hostgroup_correct(self):
        parsed = self.parser.parse(self.load_conf(GROUP_CORRECT, 'host'))
        assert len(parsed) == 1
        group = parsed[0]
        assert isinstance(group, entities.FreeIPAUserGroup)
        assert group.name == 'group-one-hosts'
        assert group.data == {
            'description': 'Sample host group one'
        }

    def test_parse_hostgroup_correct_several(self):
        parsed = self.parser.parse(
            self.load_conf(GROUP_CORRECT_SEVERAL, 'host'))
        assert len(parsed) == 2
        assert all(isinstance(i, entities.FreeIPAUserGroup) for i in parsed)
        groups = sorted(parsed, key=lambda i: i.name)
        names = [group.name for group in groups]
        assert names == ['group-three-hosts', 'group-two']
        data = [group.data for group in groups]
        assert data[0] == {
            'description': 'Sample host group three.',
            'memberOf': ['group-two']
        }
        assert data[1] == {
            'description': 'Sample meta host group two.',
            'memberOf': ['group-one-hosts']
        }

    def test_parse_hostgroup_missingkey(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.parser.parse(self.load_conf(GROUP_MISSINGKEY, 'host'))
        assert (
            "required key not provided @ data['group-two']['description']"
            in str(exc))

    def test_parse_hostgroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.parser.parse(self.load_conf(GROUP_EXTRAKEY, 'host'))
        assert (
            "extra keys not allowed @ data['group-one-hosts']['extrakey']"
            in str(exc)
        )


class TestUserConfigParser(TestConfigParser):
    def setup_method(self, method):
        self.parser = tool.UserConfigParser()

    def test_parse_user_correct(self):
        parsed = self.parser.parse(self.load_conf(USER_CORRECT))
        assert len(parsed) == 1
        user = parsed[0]
        assert isinstance(user, entities.FreeIPAUser)
        assert user.name == 'archibald.jenkins'
        assert user.data == {
            'emailAddress': 'deli+jenkins@gooddata.com',
            'firstName': 'Archibald',
            'githubLogin': 'yenkins',
            'memberOf': [
                'github-gooddata-hackers',
                'hipchat-users',
                'ipausers',
                'jenkins',
                'jira-gooddata-users'
            ],
            'initials': 'AJE',
            'lastName': 'Jenkins',
            'manager': 'sample.manager',
            'organizationUnit': 'CISTA',
            'title': 'Sr. SW Enginner'
        }

    def test_parse_user_correct_several(self):
        parsed = self.parser.parse(self.load_conf(USER_CORRECT_SEVERAL))
        assert len(parsed) == 2
        assert all(isinstance(i, entities.FreeIPAUser) for i in parsed)
        users = sorted(parsed, key=lambda i: i.name)
        logins = [user.name for user in users]
        assert logins == ['firstname.lastname', 'firstname.lastname2']
        data = [user.data for user in users]
        assert data[0] == {
            'emailAddress': 'firstname.lastname@gooddata.com',
            'firstName': 'Firstname',
            'githubLogin': 'github-account-one',
            'initials': 'FLA',
            'lastName': 'Lastname',
            'manager': 'sample.manager',
            'memberOf': [
                'github-gooddata-hackers',
                'hipchat-users',
                'ipausers',
                'jenkins',
                'jira-gooddata-users'],
            'organizationUnit': 'CISTA',
            'title': 'Sr. SW Enginner'}
        assert data[1] == {
            'emailAddress': 'firstname.lastname2@gooddata.com',
            'firstName': 'Firstname',
            'githubLogin': 'github-account-two',
            'initials': 'FLN',
            'lastName': 'Lastname',
            'manager': 'other.manager',
            'memberOf': [
                'github-gooddata-hackers',
                'hipchat-users',
                'ipausers',
                'jenkins',
                'jira-gooddata-users'],
            'organizationUnit': 'CISTA',
            'title': 'Sr. SW Enginner'}

    def test_parse_user_missingkey(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.parser.parse(self.load_conf(USER_MISSINGKEY))
        assert (
            "required key not provided @ data['missing.key']['initials']"
            in str(exc))

    def test_parse_user_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.parser.parse(self.load_conf(USER_EXTRAKEY))
        assert (
            "extra keys not allowed @ data['extra.key']['invalid']" in str(exc)
        )


class TestUserGroupConfigParser(TestConfigParser):
    def setup_method(self, method):
        self.parser = tool.UserGroupConfigParser()

    def test_parse_usergroup_correct(self):
        parsed = self.parser.parse(self.load_conf(GROUP_CORRECT, 'user'))
        assert len(parsed) == 1
        group = parsed[0]
        assert isinstance(group, entities.FreeIPAUserGroup)
        assert group.name == 'group-one-users'
        assert group.data == {
            'description': 'Sample group one'
        }

    def test_parse_usergroup_correct_several(self):
        parsed = self.parser.parse(
            self.load_conf(GROUP_CORRECT_SEVERAL, 'user'))
        assert len(parsed) == 2
        assert all(isinstance(i, entities.FreeIPAUserGroup) for i in parsed)
        groups = sorted(parsed, key=lambda i: i.name)
        names = [group.name for group in groups]
        assert names == ['group-three-users', 'group-two']
        data = [group.data for group in groups]
        assert data[0] == {
            'description': 'Sample group three.',
            'memberOf': ['group-two']
        }
        assert data[1] == {
            'description': 'Sample meta group two.',
            'memberOf': ['group-one-users']
        }

    def test_parse_usergroup_missingkey(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.parser.parse(self.load_conf(GROUP_MISSINGKEY, 'user'))
        assert (
            "required key not provided @ data['group-two']['description']"
            in str(exc))

    def test_parse_usergroup_extrakey(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.parser.parse(self.load_conf(GROUP_EXTRAKEY, 'user'))
        assert (
            "extra keys not allowed @ data['group-one-users']['extrakey']"
            in str(exc)
        )

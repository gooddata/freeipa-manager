import logging
import os
import pytest
import sys
from testfixtures import log_capture


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('config_loader')
entities = __import__('entities')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')


class TestConfigLoader(object):
    def setup_method(self, method):
        self.loader = tool.ConfigLoader(CONFIG_CORRECT)
        self.expected_hostgroups = [
            CONFIG_CORRECT + '/hostgroups/%s.yaml' % group
            for group in ['group_one', 'several']]
        self.expected_users = [
            CONFIG_CORRECT + '/users/%s.yaml' % user
            for user in ['archibald_jenkins', 'several']]
        self.expected_usergroups = [
            CONFIG_CORRECT + '/usergroups/%s.yaml' % group
            for group in ['group_one', 'several']]

    def test_retrieve_paths_all(self):
        paths = self.loader._retrieve_paths()
        assert sorted(paths.keys()) == ['hostgroups', 'usergroups', 'users']
        assert sorted(paths.get('hostgroups')) == self.expected_hostgroups
        assert sorted(paths.get('users')) == self.expected_users
        assert sorted(paths.get('usergroups')) == self.expected_usergroups

    def test_retrieve_paths_users(self):
        paths = self.loader._retrieve_paths(['users'])
        assert paths.keys() == ['users']
        assert sorted(paths.get('users')) == self.expected_users

    def test_retrieve_paths_usergroups(self):
        paths = self.loader._retrieve_paths(['usergroups'])
        assert paths.keys() == ['usergroups']
        assert sorted(paths.get('usergroups')) == self.expected_usergroups

    @log_capture('ConfigLoader', level=logging.WARNING)
    def test_retrieve_paths_invalid_entity(self, captured_log):
        paths = self.loader._retrieve_paths(['non-existent-entity'])
        assert paths.keys() == []
        captured_log.check(
            ('ConfigLoader', 'WARNING', 'No non-existent-entity files found'))

    def test_check_data(self):
        self.loader.entities = {'users': {}}
        data = {
            'archibald.jenkins': {}
        }
        self.loader._check_data(data, 'users')

    def test_check_data_empty(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._check_data(None, 'users')
        assert exc.value[0] == 'Empty config file'

    def test_check_data_bad_format(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._check_data([{'archibald.jenkins': {}}], 'users')
        assert exc.value[0] == 'Must be a dictionary of entities'

    def test_check_data_duplicit_entity(self):
        self.loader.entities = {
            'users': [entities.FreeIPAUser('archibald.jenkins', {})]
        }
        data = {
            'archibald.jenkins': {}
        }
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._check_data(data, 'users')
        assert exc.value[0] == 'Duplicit definition of archibald.jenkins'

    @log_capture('ConfigLoader', level=logging.WARNING)
    def test_load(self, captured_log):
        self.loader.basepath = CONFIG_CORRECT
        self.loader.load()
        hostgroups = self.loader.entities['hostgroups']
        assert len(hostgroups) == 3
        assert set(group.name for group in hostgroups) == set([
            'group-one-hosts', 'group-two', 'group-three-hosts'])
        users = self.loader.entities['users']
        assert len(users) == 3
        assert sorted(user.name for user in users) == [
            'archibald.jenkins', 'firstname.lastname', 'firstname.lastname2']
        usergroups = self.loader.entities['usergroups']
        assert len(usergroups) == 3
        assert set(group.name for group in usergroups) == set([
            'group-one-users', 'group-two', 'group-three-users'])
        captured_log.check(
            ('ConfigLoader', 'WARNING',
             'More than one entity parsed from hostgroups/several.yaml (2).'),
            ('ConfigLoader', 'WARNING',
             'More than one entity parsed from usergroups/several.yaml (2).'),
            ('ConfigLoader', 'WARNING',
             'More than one entity parsed from users/several.yaml (2).'))

    def test_parse_hostgroups(self):
        assert self.loader._parse({}, 'hostgroups') == []

    def test_parse_usergroups(self):
        assert self.loader._parse({}, 'usergroups') == []

    def test_parse_users(self):
        assert self.loader._parse({}, 'users') == []

    def test_parse_invalid_type(self):
        with pytest.raises(tool.ManagerError) as exc:
            self.loader._parse({}, 'non-existent-entity')
        assert exc.value[0] == 'No parser configured for non-existent-entity'

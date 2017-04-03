import os
import pytest
import sys


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('entity_loader')
entities = __import__('entities')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')


class TestEntityLoader(object):
    def setup_method(self, method):
        self.loader = tool.EntityLoader(CONFIG_CORRECT)
        self.expected_users = [
            CONFIG_CORRECT + '/users/' + user
            for user in ['archibald_jenkins.yaml', 'several.yaml']]

    def test_retrieve_paths_all(self):
        paths = self.loader._retrieve_paths()
        assert sorted(paths.keys()) == ['users']
        assert sorted(paths.get('users')) == self.expected_users

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

    def test_load(self):
        self.loader.basepath = CONFIG_CORRECT
        self.loader.load()
        users = self.loader.entities['users']
        assert len(users) == 3
        assert sorted(user.name for user in users) == [
            'archibald.jenkins', 'firstname.lastname', 'firstname.lastname2']

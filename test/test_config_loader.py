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
CONFIG_INVALID = os.path.join(testpath, 'freeipa-manager-config/invalid')
DOMAIN = 'intgdc.com'


class TestConfigLoader(object):
    def setup_method(self, method):
        self.loader = tool.ConfigLoader(CONFIG_CORRECT, DOMAIN)
        self.expected_hostgroups = [
            CONFIG_CORRECT + '/hostgroups/%s.yaml' % group
            for group in ['group_one', 'several']]
        self.expected_users = [
            CONFIG_CORRECT + '/users/%s.yaml' % user
            for user in ['archibald_jenkins', 'several']]
        self.expected_usergroups = [
            CONFIG_CORRECT + '/usergroups/%s.yaml' % group
            for group in ['group_one', 'several']]
        self.expected_hbac_rules = [
            CONFIG_CORRECT + '/hbacrules/%s.yaml' % rule
            for rule in ['rule_one', 'several']]
        self.expected_sudo_rules = [
            CONFIG_CORRECT + '/sudorules/%s.yaml' % rule
            for rule in ['rule_one', 'several']]

    def test_retrieve_paths(self):
        paths = self.loader._retrieve_paths()
        assert sorted(paths.keys()) == [
            'HBAC rules', 'hostgroups', 'sudo rules', 'usergroups', 'users']
        assert sorted(paths['hostgroups']) == self.expected_hostgroups
        assert sorted(paths['users']) == self.expected_users
        assert sorted(paths['usergroups']) == self.expected_usergroups
        assert sorted(paths['HBAC rules']) == self.expected_hbac_rules
        assert sorted(paths['sudo rules']) == self.expected_sudo_rules

    @log_capture('ConfigLoader', level=logging.WARNING)
    def test_retrieve_paths_empty(self, captured_warnings):
        self.loader.basepath = '/dev/null'
        paths = self.loader._retrieve_paths()
        assert paths.keys() == []
        assert set(i.msg % i.args for i in captured_warnings.records) == set([
            'No HBAC rules files found',
            'No hostgroups files found',
            'No sudo rules files found',
            'No usergroups files found',
            'No users files found'])

    def test_parse(self):
        self.loader.entities = {'users': []}
        data = {'archibald.jenkins': {}}
        self.loader._parse(
            data, entities.FreeIPAUser, 'users/archibald_jenkins.yaml')

    def test_parse_empty(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._parse(
                {}, entities.FreeIPAUser, 'users/archibald_jenkins.yaml')
        assert exc.value[0] == 'Config must be a non-empty dictionary'

    def test_parse_bad_data_format(self):
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._parse(
                [{'archibald.jenkins': {}}],
                entities.FreeIPAUser, 'users/archibald_jenkins.yaml')
        assert exc.value[0] == 'Config must be a non-empty dictionary'

    def test_parse_duplicit_entities(self):
        data = {'archibald.jenkins': {}}
        self.loader.entities = {
            'users': [entities.FreeIPAUser('archibald.jenkins', {}, DOMAIN)]}
        with pytest.raises(tool.ConfigError) as exc:
            self.loader._parse(
                data, entities.FreeIPAUser, 'users/archibald_jenkins.yaml')
        assert exc.value[0] == 'Duplicit definition of archibald.jenkins'

    @log_capture('ConfigLoader', level=logging.WARNING)
    def test_load(self, captured_warnings):
        self.loader.basepath = CONFIG_CORRECT
        self.loader.load()
        hostgroups = self.loader.entities['hostgroups']
        assert len(hostgroups) == 3
        assert set(g.name for g in hostgroups) == set([
            'group-one-hosts', 'group-two', 'group-three-hosts'])
        users = self.loader.entities['users']
        assert len(users) == 3
        assert sorted(u.name for u in users) == [
            'archibald.jenkins', 'firstname.lastname', 'firstname.lastname2']
        usergroups = self.loader.entities['usergroups']
        assert len(usergroups) == 3
        assert set(g.name for g in usergroups) == set([
            'group-one-users', 'group-two', 'group-three-users'])
        assert set(i.msg % i.args for i in captured_warnings.records) == set([
            'More than one entity parsed from hbacrules/several.yaml (2)',
            'More than one entity parsed from hostgroups/several.yaml (2)',
            'More than one entity parsed from sudorules/several.yaml (2)',
            'More than one entity parsed from usergroups/several.yaml (2)',
            'More than one entity parsed from users/several.yaml (2)'])

    @log_capture('ConfigLoader', level=logging.WARNING)
    def test_load_empty(self, captured_warnings):
        self.loader.basepath = '/dev/null'
        self.loader.load()
        assert self.loader.entities == dict()
        assert set(i.msg % i.args for i in captured_warnings.records) == set([
            'No HBAC rules files found',
            'No hostgroups files found',
            'No sudo rules files found',
            'No usergroups files found',
            'No users files found'])

    def test_load_invalid(self):
        self.loader.basepath = CONFIG_INVALID
        with pytest.raises(tool.ConfigError) as exc:
            self.loader.load()
        err = exc.value[0]
        for i in [
                'hbacrules/extrakey.yaml', 'hostgroups/extrakey.yaml',
                'hostgroups/invalidmember.yaml', 'sudorules/extrakey.yaml',
                'usergroups/extrakey.yaml', 'usergroups/invalidmember.yaml',
                'users/extrakey.yaml', 'users/invalidmember.yaml']:
            assert i in err
        assert ('users/duplicit.yaml' in err or
                'users/duplicit2.yaml' in err)

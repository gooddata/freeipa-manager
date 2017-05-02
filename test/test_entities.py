import mock
import os
import pytest
import sys
import yaml


testpath = os.path.dirname(os.path.abspath(__file__))

toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('entities')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')
USER_CORRECT = os.path.join(CONFIG_CORRECT, 'users/archibald_jenkins.yaml')
GROUP_CORRECT = os.path.join(CONFIG_CORRECT, '%sgroups/group_one.yaml')


class TestFreeIPAEntityBase(object):
    def load_conf(self, path, *args):
        with open(path % args, 'r') as src:
            return yaml.safe_load(src)


class TestFreeIPAEntity(TestFreeIPAEntityBase):
    def test_create_entity(self):
        with pytest.raises(TypeError) as exc:
            tool.FreeIPAEntity('sample.entity', {})
        assert exc.value[0] == (
            "Can't instantiate abstract class FreeIPAEntity "
            "with abstract methods _construct_dn")


class TestFreeIPAGroup(TestFreeIPAEntityBase):
    def test_create_group(self):
        with pytest.raises(TypeError) as exc:
            tool.FreeIPAGroup('sample-group', {})
        assert exc.value[0] == (
            "Can't instantiate abstract class FreeIPAGroup "
            "with abstract methods _construct_dn")

    def test_create_usergroup_nonmeta(self):
        group = tool.FreeIPAUserGroup('sample-group-users', {})
        assert not group.is_meta

    def test_create_usergroup_meta(self):
        group = tool.FreeIPAUserGroup('sample-group', {})
        assert group.is_meta

    def test_create_usergroup_meta_not_enforced(self):
        with mock.patch('entities.FreeIPAUserGroup.meta_group_suffix', ''):
            group = tool.FreeIPAUserGroup('sample-group', {})
            assert not group.is_meta

    def test_create_hostgroup_nonmeta(self):
        group = tool.FreeIPAHostGroup('sample-group-hosts', {})
        assert not group.is_meta

    def test_create_hostgroup_meta_not_enforced(self):
        with mock.patch('entities.FreeIPAHostGroup.meta_group_suffix', ''):
            group = tool.FreeIPAHostGroup('sample-group', {})
            assert not group.is_meta

    def test_create_hostgroup_meta(self):
        group = tool.FreeIPAHostGroup('sample-group', {})
        assert group.is_meta


class TestFreeIPAUser(TestFreeIPAEntityBase):
    def test_adjust_data_same(self):
        data = {'manager': 'sample.manager'}
        user = tool.FreeIPAUser('firstname.lastname', dict(data))
        user._adjust_data()
        assert user.data == data

    def test_adjust_data_different(self):
        data = {
            'manager': (
                'uid=sample.manager,cn=users,cn=accounts,dc=intgdc,dc=com')}
        user = tool.FreeIPAUser('firstname.lastname', dict(data))
        user._adjust_data()
        assert user.data == {'manager': 'sample.manager'}

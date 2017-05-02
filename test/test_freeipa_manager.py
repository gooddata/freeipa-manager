import logging
import mock
import os
import pytest
import sys
from testfixtures import log_capture


testpath = os.path.dirname(os.path.abspath(__file__))
toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
sys.modules['ldap'] = mock.Mock()
tool = __import__('freeipa_manager')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')
CONFIG_INVALID = os.path.join(testpath, 'freeipa-manager-config/invalid')


class TestFreeIPAManagerBase(object):
    def _init_tool(self, args):
        with mock.patch.object(sys, 'argv', ['manager'] + args):
            return tool.FreeIPAManager()


class TestFreeIPAManagerRequirementCheck(TestFreeIPAManagerBase):
    def test_check(self):
        manager = self._init_tool(
            ['check', '-c', CONFIG_CORRECT, '-r', 'ipa01.devgdc.com'])
        manager._check_requirements()

    def test_check_no_conf(self):
        manager = self._init_tool(['check', '-r', 'ipa01.devgdc.com'])
        manager._check_requirements()

    def test_check_no_remote(self):
        manager = self._init_tool(['check', '-c', CONFIG_CORRECT])
        manager._check_requirements()

    def test_check_no_args(self):
        manager = self._init_tool(['check'])
        with pytest.raises(tool.ManagerError) as exc:
            manager._check_requirements()
        assert exc.value[0] == '--conf or --remote required'

    def test_compare(self):
        manager = self._init_tool(
            ['compare', '-c', CONFIG_CORRECT, '-r', 'ipa01.devgdc.com'])
        manager._check_requirements()

    def test_compare_no_conf(self):
        manager = self._init_tool(['compare', '-r', 'ipa01.devgdc.com'])
        with pytest.raises(tool.ManagerError) as exc:
            manager._check_requirements()
        assert exc.value[0] == 'Both --conf and --remote required'

    def test_compare_no_remote(self):
        manager = self._init_tool(['compare', '-c', CONFIG_CORRECT])
        with pytest.raises(tool.ManagerError) as exc:
            manager._check_requirements()
        assert exc.value[0] == 'Both --conf and --remote required'

    def test_compare_no_args(self):
        manager = self._init_tool(['compare'])
        with pytest.raises(tool.ManagerError) as exc:
            manager._check_requirements()
        assert exc.value[0] == 'Both --conf and --remote required'

    def test_pull(self):
        manager = self._init_tool(
            ['pull', '-c', CONFIG_CORRECT, '-r', 'ipa01.devgdc.com'])
        manager._check_requirements()

    def test_pull_no_conf(self):
        manager = self._init_tool(['pull', '-r', 'ipa01.devgdc.com'])
        with pytest.raises(tool.ManagerError) as exc:
            manager._check_requirements()
        assert exc.value[0] == 'Both --conf and --remote required'

    def test_pull_no_remote(self):
        manager = self._init_tool(['pull', '-c', CONFIG_CORRECT])
        with pytest.raises(tool.ManagerError) as exc:
            manager._check_requirements()
        assert exc.value[0] == 'Both --conf and --remote required'

    def test_pull_no_args(self):
        manager = self._init_tool(['pull'])
        with pytest.raises(tool.ManagerError) as exc:
            manager._check_requirements()
        assert exc.value[0] == 'Both --conf and --remote required'

    def test_push(self):
        manager = self._init_tool(
            ['push', '-c', CONFIG_CORRECT, '-r', 'ipa01.devgdc.com'])
        manager._check_requirements()

    def test_push_no_conf(self):
        manager = self._init_tool(['push', '-r', 'ipa01.devgdc.com'])
        with pytest.raises(tool.ManagerError) as exc:
            manager._check_requirements()
        assert exc.value[0] == 'Both --conf and --remote required'

    def test_push_no_remote(self):
        manager = self._init_tool(['push', '-c', CONFIG_CORRECT])
        with pytest.raises(tool.ManagerError) as exc:
            manager._check_requirements()
        assert exc.value[0] == 'Both --conf and --remote required'

    def test_push_no_args(self):
        manager = self._init_tool(['push'])
        with pytest.raises(tool.ManagerError) as exc:
            manager._check_requirements()
        assert exc.value[0] == 'Both --conf and --remote required'


class TestFreeIPAManagerRun(TestFreeIPAManagerBase):
    def test_run_check(self):
        manager = self._init_tool(
            ['check', '-c', CONFIG_CORRECT, '-r', 'ipa01.devgdc.com'])
        manager._load_config = mock.Mock()
        manager._load_ldap = mock.Mock()
        manager.run()
        assert manager._load_config.called
        assert manager._load_ldap.called

    def test_run_check_conf(self):
        manager = self._init_tool(['check', '--conf', CONFIG_CORRECT])
        manager._load_config = mock.Mock()
        manager._load_ldap = mock.Mock()
        manager.run()
        assert manager._load_config.called
        assert not manager._load_ldap.called

    def test_run_check_conf_missing_arg(self):
        manager = self._init_tool(['check'])
        with pytest.raises(SystemExit) as exc:
            manager.run()
        assert exc.value[0] == 2

    @log_capture('FreeIPAManager', level=logging.ERROR)
    def test_run_check_conf_invalid(self, captured_log):
        manager = self._init_tool(['check', '--conf', CONFIG_INVALID])
        with pytest.raises(SystemExit) as exc:
            manager.run()
        assert exc.value[0] == 1
        captured_log.check(
            ('FreeIPAManager', 'ERROR',
             ('There have been errors in 3 configuration files: '
              '[hostgroups/extrakey.yaml, usergroups/extrakey.yaml, '
              'users/extrakey.yaml]')))

    def test_run_check_ldap(self):
        manager = self._init_tool(['check', '-r', 'ipa01.devgdc.com'])
        with mock.patch('freeipa_manager.LdapDownloader') as mock_loader:
            manager.run()
            mock_loader.assert_called_with('ipa01.devgdc.com')
            manager.ldap_loader.load_entities.assert_called_with(
                manager.args.types)

    def test_run_compare(self):
        manager = self._init_tool(
            ['compare', '-c', CONFIG_CORRECT, '-r', 'ipa01.devgdc.com'])
        manager.compare = mock.Mock()
        manager.run()
        assert manager.compare.called

    def test_run_pull(self):
        manager = self._init_tool(
            ['pull', '-c', CONFIG_CORRECT, '-r', 'ipa01.devgdc.com'])
        manager.pull = mock.Mock()
        manager.run()
        assert manager.pull.called

    def test_run_push(self):
        manager = self._init_tool(
            ['push', '-c', CONFIG_CORRECT, '-r', 'ipa01.devgdc.com'])
        manager.push = mock.Mock()
        manager.run()
        assert manager.push.called

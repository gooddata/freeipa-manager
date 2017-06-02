import logging
import mock
import os
import pytest
import sys
from testfixtures import log_capture


testpath = os.path.dirname(os.path.abspath(__file__))
toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
for module in ['ldap', 'dns', 'dns.resolver']:
    sys.modules[module] = mock.Mock()
tool = __import__('freeipa_manager')

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')
CONFIG_INVALID = os.path.join(testpath, 'freeipa-manager-config/invalid')


class TestFreeIPAManagerBase(object):
    def _init_tool(self, args):
        with mock.patch.object(sys, 'argv', ['manager'] + args):
            return tool.FreeIPAManager()


class TestFreeIPAManagerRun(TestFreeIPAManagerBase):
    def test_run_check(self):
        manager = self._init_tool([CONFIG_CORRECT, 'check', '-d'])
        manager._load_config = mock.Mock()
        with mock.patch('freeipa_manager.LdapDownloader') as mock_ldap:
            manager.run()
            mock_ldap.assert_called_with('intgdc.com')
        assert manager._load_config.called

    def test_run_check_ipa_domain(self):
        manager = self._init_tool(
            [CONFIG_CORRECT, 'check', '-d', 'devgdc.com'])
        manager._load_config = mock.Mock()
        with mock.patch('freeipa_manager.LdapDownloader') as mock_ldap:
            manager.run()
            mock_ldap.assert_called_with('devgdc.com')
        assert manager._load_config.called

    def test_run_check_local(self):
        manager = self._init_tool([CONFIG_CORRECT, 'check'])
        manager._load_config = mock.Mock()
        with mock.patch('freeipa_manager.LdapDownloader') as mock_ldap:
            manager.run()
            mock_ldap.assert_called_with('localhost')
        assert manager._load_config.called

    @log_capture('FreeIPAManager', level=logging.ERROR)
    def test_run_check_local_invalid(self, captured_log):
        manager = self._init_tool([CONFIG_INVALID, 'check'])
        with pytest.raises(SystemExit) as exc:
            manager.run()
        assert exc.value[0] == 1
        records = [i.msg for i in captured_log.records]
        assert len(records) == 1
        config_err = str(records[0])
        assert 'There have been errors in 9 configuration files' in config_err
        for i in [
                'hbacrules/extrakey.yaml', 'hostgroups/extrakey.yaml',
                'hostgroups/invalidmember.yaml', 'sudorules/extrakey.yaml',
                'usergroups/extrakey.yaml', 'usergroups/invalidmember.yaml',
                'users/extrakey.yaml', 'users/invalidmember.yaml']:
            assert i in config_err
        assert ('users/duplicit.yaml' in config_err or
                'users/duplicit2.yaml' in config_err)

    def test_run_compare(self):
        manager = self._init_tool([CONFIG_CORRECT, 'compare'])
        manager.compare = mock.Mock()
        manager.run()
        assert manager.compare.called

    def test_run_pull(self):
        manager = self._init_tool([CONFIG_CORRECT, 'pull'])
        manager.pull = mock.Mock()
        manager.run()
        assert manager.pull.called

    def test_run_push(self):
        manager = self._init_tool([CONFIG_CORRECT, 'push'])
        manager.push = mock.Mock()
        manager.run()
        assert manager.push.called

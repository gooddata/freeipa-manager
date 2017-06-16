import logging
import mock
import os
import pytest
import sys
from testfixtures import log_capture


testpath = os.path.dirname(os.path.abspath(__file__))
toolpath = testpath.replace('test', 'src')
sys.path.insert(0, toolpath)
tool = __import__('freeipa_manager')
errors = __import__('errors')


class TestFreeIPAManagerBase(object):
    def _init_tool(self, args):
        with mock.patch.object(sys, 'argv', ['manager', 'config_path'] + args):
            return tool.FreeIPAManager()


class TestFreeIPAManagerRun(TestFreeIPAManagerBase):
    @mock.patch('freeipa_manager.LdapDownloader')
    @mock.patch('freeipa_manager.IntegrityChecker')
    @mock.patch('freeipa_manager.ConfigLoader')
    def test_run_check(self, mock_config, mock_check, mock_ldap):
        manager = self._init_tool(['check', '-d', '-r', 'rules_path'])
        manager.run()
        mock_config.assert_called_with('config_path', 'intgdc.com')
        mock_check.assert_called()
        mock_ldap.assert_called_with('intgdc.com')

    def test_run_check_ipa_domain(self):
        manager = self._init_tool(['check', '-d', 'devgdc.com'])
        manager._load_config = mock.Mock()
        with mock.patch('freeipa_manager.LdapDownloader') as mock_ldap:
            manager.run()
            mock_ldap.assert_called_with('devgdc.com')
        manager._load_config.assert_called()

    def test_run_check_local(self):
        manager = self._init_tool(['check'])
        manager._load_config = mock.Mock()
        with mock.patch('freeipa_manager.LdapDownloader') as mock_ldap:
            manager.run()
            mock_ldap.assert_called_with('localhost')
        manager._load_config.assert_called()

    @log_capture('FreeIPAManager', level=logging.ERROR)
    def test_run_check_error(self, captured_errors):
        with mock.patch('freeipa_manager.ConfigLoader.load') as mock_load:
            mock_load.side_effect = errors.ConfigError('Error loading config')
            with pytest.raises(SystemExit) as exc:
                self._init_tool(['check']).run()
        assert exc.value[0] == 1
        captured_errors.check(
            ('FreeIPAManager', 'ERROR', 'Error loading config'))

    def test_run_compare(self):
        manager = self._init_tool(['compare'])
        with pytest.raises(NotImplementedError) as exc:
            manager.run()
        assert exc.value[0] == 'Comparing not available yet.'

    def test_run_pull(self):
        manager = self._init_tool(['pull'])
        with pytest.raises(NotImplementedError) as exc:
            manager.run()
        assert exc.value[0] == 'Config pulling not available yet.'

    def test_run_push(self):
        manager = self._init_tool(['push'])
        with pytest.raises(NotImplementedError) as exc:
            manager.run()
        assert exc.value[0] == 'Config pushing not available yet.'

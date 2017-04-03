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

CONFIG_CORRECT = os.path.join(testpath, 'freeipa-manager-config/correct')
CONFIG_INVALID = os.path.join(testpath, 'freeipa-manager-config/invalid')


class TestFreeIPAManager(object):
    def _init_tool(self, args):
        with mock.patch.object(sys, 'argv', ['manager'] + args):
            return tool.FreeIPAManager()

    def test_run_load(self):
        manager = self._init_tool([CONFIG_CORRECT])
        manager._load_entities = mock.Mock()
        manager.run()
        assert manager._load_entities.called

    def test_run_load_correct(self):
        manager = self._init_tool([CONFIG_CORRECT])
        manager.run()
        assert manager.loader.entities.keys() == ['users']
        logins = [e.name for e in manager.loader.entities['users']]
        assert sorted(logins) == [
            'archibald.jenkins', 'firstname.lastname', 'firstname.lastname2']

    @log_capture('FreeIPAManager', level=logging.ERROR)
    def test_run_load_invalid(self, captured_log):
        manager = self._init_tool([CONFIG_INVALID])
        with pytest.raises(SystemExit) as exc:
            manager.run()
        assert exc.value[0] == 1
        captured_log.check(
            ('FreeIPAManager', 'ERROR',
             ('There have been errors in 2 configuration files: '
              '[users/extrakey.yaml, users/missingkey.yaml]')))

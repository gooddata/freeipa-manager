import logging
import os.path
import pytest
from testfixtures import log_capture

from _utils import _import
tool = _import('ipamanager', 'difference')
testpath = os.path.dirname(os.path.abspath(__file__))

PROD_PATH = os.path.join(testpath, 'freeipa-manager-config/diff/prod')
INT_PATH = os.path.join(testpath, 'freeipa-manager-config/diff/int')


class TestDiff(object):
    def test_incorrect(self):
        with pytest.raises(tool.IntegrityError) as exc:
            tool.FreeIPADifference(INT_PATH, PROD_PATH).run()
        assert exc.value[0] == 'The ADDITIONAL entities are : additional.yaml'

    @log_capture('FreeIPADifference', level=logging.INFO)
    def test_correct(self, captured_log):
        tool.FreeIPADifference(PROD_PATH, INT_PATH).run()
        captured_log.check(('FreeIPADifference', 'INFO', 'There are no ADDITIONAL entites'),)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.

import logging
import pytest
from testfixtures import log_capture

from _utils import _import
tool = _import('ipamanager', 'alerting')
modulename = 'ipamanager.alerting'


class DummyAlertingPlugin(tool.AlertingPlugin):
    def dispatch(self):
        self.lg.debug('Sent %d messages to /dev/null', len(self.messages))


class TestAlerting(object):
    def setup_method(self, method):
        if not method.func_name.endswith('abstract'):
            self.plugin = DummyAlertingPlugin(logging.WARNING)

    def test_init_abstract(self):
        with pytest.raises(TypeError) as exc:
            tool.AlertingPlugin(logging.WARNING)
        assert exc.value[0] == (
            "Can't instantiate abstract class AlertingPlugin "
            "with abstract methods dispatch")

    def test_init(self):
        assert self.plugin.name == 'DummyAlertingPlugin'
        assert self.plugin.level == logging.WARNING
        assert self.plugin.messages == []
        assert self.plugin.max_level == logging.NOTSET

    def test_emit(self):
        record = logging.LogRecord(
            'IpaManager', logging.ERROR, 'ipamanager.py', 42,
            'error updating user %s', ('user1',), None)
        self.plugin.emit(record)
        assert self.plugin.messages == ['ERROR: error updating user user1']
        assert self.plugin.max_level == logging.ERROR

    def test_log_info(self):
        logger = logging.getLogger('test')
        logger.handlers = [self.plugin]
        logger.info('test info log')
        assert self.plugin.messages == []
        assert self.plugin.max_level == logging.NOTSET

    def test_log_warning(self):
        logger = logging.getLogger('test')
        logger.handlers = [self.plugin]
        logger.warning('test warn log')
        assert self.plugin.messages == ['WARNING: test warn log']
        assert self.plugin.max_level == logging.WARNING

    def test_log_error(self):
        logger = logging.getLogger('test')
        logger.handlers = [self.plugin]
        logger.error('test err log')
        assert self.plugin.messages == ['ERROR: test err log']
        assert self.plugin.max_level == logging.ERROR

    def test_log_multiple(self):
        logger = logging.getLogger('ManagerModule')
        logger.handlers = [self.plugin]
        logger.error('test err log')
        logger.warning('test warn log')
        logger.info('test info log')
        assert self.plugin.messages == [
            'ERROR: test err log', 'WARNING: test warn log']
        assert self.plugin.max_level == logging.ERROR

    @log_capture('DummyAlertingPlugin')
    def test_dispatch(self, log):
        self.plugin.messages = ['ERROR: something', 'WARNING: other thing']
        self.plugin.dispatch()
        log.check(('DummyAlertingPlugin', 'DEBUG',
                   'Sent 2 messages to /dev/null'))

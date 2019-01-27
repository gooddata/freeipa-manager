#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.

import logging
import mock
import pytest
from testfixtures import log_capture

from _utils import _import
tool = _import('ipamanager', 'command')


class TestCommand(object):
    def test_create_command(self):
        cmd = tool.Command(
            'test_cmd', {'attr1': u'value1', 'attr2': ('value21', 'value22')},
            'entity', 'cn')
        payload = {'attr1': u'value1', 'attr2': (u'value21', u'value22'),
                   'cn': 'entity'}
        desc = "test_cmd entity (attr1=value1; attr2=(u'value21', u'value22'))"
        assert cmd.command == 'test_cmd'
        assert cmd.payload == payload
        assert isinstance(cmd.payload['attr1'], unicode)
        assert isinstance(cmd.payload['attr2'][0], unicode)
        assert cmd.description == desc

    @log_capture('Command', level=logging.INFO)
    def test_execute(self, captured_log):
        mock_api = mock.MagicMock()
        mock_api.Command.__getitem__.side_effect = self._api_call
        tool.Command('user_add', {'givenName': 'Test', 'sn': 'User'},
                     't.user', 'uid').execute(mock_api)
        captured_log.check(
            ('Command', 'INFO',
             u'Executing user_add t.user (givenname=Test; sn=User)'),
            ('Command', 'INFO', u'Added user "t.user"'))

    @log_capture('Command', level=logging.INFO)
    def test_execute_nosummary(self, captured_log):
        mock_api = mock.MagicMock()
        mock_api.Command.__getitem__.side_effect = self._api_call
        tool.Command('group_add_member', {'user': 'user1'},
                     'group1', 'cn').execute(mock_api)
        captured_log.check(
            ('Command', 'INFO',
             u'Executing group_add_member group1 (user=user1)'),
            ('Command', 'INFO',
             u'group_add_member group1 (user=user1) successful'))

    @log_capture('Command', level=logging.INFO)
    def test_execute_fail(self, captured_log):
        mock_api = mock.MagicMock()
        mock_api.Command.__getitem__.side_effect = self._api_call_unreliable
        cmd = tool.Command(
            'group_add_member', {'user': 'user1'}, 'group1', 'cn')
        with pytest.raises(tool.CommandError) as exc:
            cmd.execute(mock_api)
        assert exc.value[0] == (
            "Error executing group_add_member: [u'- test: no such attr2']")
        captured_log.check(
            ('Command', 'INFO',
             u'Executing group_add_member group1 (user=user1)'),
            ('Command', 'ERROR',
             u'group_add_member group1 (user=user1) failed:'),
            ('Command', 'ERROR', u'- test: no such attr2'))

    def test_execute_exception(self):
        mock_api = mock.MagicMock()
        mock_api.Command.__getitem__.side_effect = self._api_call_execute_fail
        cmd = tool.Command(
            'group_add_member', {'user': 'user1'}, 'group1', 'cn')
        with pytest.raises(tool.CommandError) as exc:
            cmd.execute(mock_api)
        assert exc.value[0] == (
            'Error executing group_add_member: Some error happened')

    def test_execute_invalid_command(self):
        mock_api = mock.MagicMock()
        mock_api.Command.__getitem__.side_effect = self._api_call_execute_fail
        cmd = tool.Command('non_existent', {}, 'x', 'cn')
        with pytest.raises(tool.CommandError) as exc:
            cmd.execute(mock_api)
        assert exc.value[0] == 'Non-existent command non_existent'

    @log_capture('Command', level=logging.INFO)
    def test_handle_command_output_summary(self, captured_log):
        cmd = tool.Command('test', {'user': 'user1'}, 'group1', 'cn')
        cmd._handle_output({'summary': u'Updated successfully.'})
        captured_log.check(('Command', 'INFO', u'Updated successfully.'))

    @log_capture('Command', level=logging.INFO)
    def test_handle_command_output_no_summary(self, captured_log):
        cmd = tool.Command('test', {'user': 'user1'}, 'group1', 'cn')
        cmd._handle_output(
            {u'failed': {u'member': {u'user': (), u'group': ()}}})
        captured_log.check(
            ('Command', 'INFO', u'test group1 (user=user1) successful'))

    @log_capture('Command', level=logging.INFO)
    def test_handle_command_output_error(self, captured_log):
        cmd = tool.Command('test', {'user': 'user1'}, 'group1', 'cn')
        with pytest.raises(tool.CommandError) as exc:
            cmd._handle_output({u'failed': {u'member': {
                u'user': (),
                u'group': ((u'test_group_2', u'no such entry'),)}}})
        assert exc.value[0] == ['- test_group_2: no such entry']
        captured_log.check(
            ('Command', 'ERROR', u'test group1 (user=user1) failed:'),
            ('Command', 'ERROR', u'- test_group_2: no such entry'))

    def _api_call(self, command):
        return {
            'user_add': self._api_user_add,
            'group_add_member': self._api_nosummary,
        }[command]

    def _api_call_unreliable(self, command):
        return {
            'group_add_member': self._api_fail,
        }[command]

    def _api_call_execute_fail(self, command):
        if command == 'group_add_member':
            return self._api_exc
        return self._api_call(command)

    def _api_user_add(self, **kwargs):
        return {'summary': u'Added user "%s"' % kwargs.get('uid')}

    def _api_nosummary(self, **kwargs):
            return {u'failed': {u'attr1': {'param1': (), 'param2': ()}}}

    def _api_fail(self, **kwargs):
            return {
                u'failed': {
                    u'attr1': {'param1': ((u'test', u'no such attr2'),)}}}

    def _api_exc(self, **kwargs):
        raise Exception('Some error happened')

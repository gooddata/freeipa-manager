#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.

import json
import mock
import os.path
import requests_mock
from testfixtures import LogCapture, StringComparison

from _utils import _import
tool = _import('ipamanager', 'okta_loader')
entities = _import('ipamanager', 'entities')
utils = _import('ipamanager', 'utils')
modulename = 'ipamanager.config_loader'
testpath = os.path.dirname(os.path.abspath(__file__))


class TestConfigLoader(object):
    def setup_method(self, method):
        settings = {'okta': {
            'auth': {'org': 'testoktaorg', 'token_path': '/test/okta.token'},
            'ignore': ['admin', 'user1'],
            'attributes': ['email', 'firstName', 'lastName',
                           'initials', 'githubLogin'],
            'user_id_regex': '(.+)@devgdc.com'
        }}
        ipa_groups = ['ipagroup1', 'ipagroup2', 'commongroup1', 'commongroup2']
        with mock.patch('__builtin__.open',
                        mock.mock_open(read_data='okta-token-1\n')):
            self.loader = tool.OktaLoader(settings, ipa_groups)

    def test_init(self):
        assert self.loader.ipa_groups == {
            'commongroup1', 'commongroup2', 'ipagroup1', 'ipagroup2'}
        assert self.loader.ignored == {'user': ['admin', 'user1']}
        assert self.loader.okta_org == 'testoktaorg'
        assert self.loader.okta_token == 'okta-token-1'
        assert self.loader.session.headers == {
            'Accept': 'application/json',
            'Authorization': 'SSWS okta-token-1',
            'Content-Type': 'application/json'
        }

    def _mock_groups(self, user):
        user_groups = {
            '00u99999999999999999': [
                'oktagroup1', 'oktagroup2', 'commongroup1'],
            '00u99999999999999991': ['oktagroup3', 'commongroup2']
        }
        return user_groups.get(user['id'], [])

    def test_load(self):
        self.loader._get_okta_api_pages = mock.Mock()
        with open(os.path.join(testpath, 'okta/users.json')) as resp_users_fh:
            resp_users = json.load(resp_users_fh)
            self.loader._get_okta_api_pages.return_value = resp_users
        self.loader._user_groups = self._mock_groups

        with LogCapture() as log:
            users = self.loader.load()

        assert set(users.keys()) == {u'some.user', u'other.user'}

        assert users[u'some.user'].data_ipa == {
            'givenname': (u'Some',), 'mail': (u'some.user@devgdc.com',),
            'memberof': {'group': ['commongroup1']}, 'sn': (u'User',),
            'nsaccountlock': False}
        assert users[u'some.user'].data_repo == {
            'email': u'some.user@devgdc.com', 'firstName': u'Some',
            'lastName': u'User', 'memberOf': {'group': ['commongroup1']},
            'disabled': False}

        assert users[u'other.user'].data_ipa == {
            'givenname': (u'Other',), 'mail': (u'other.user@devgdc.com',),
            'memberof': {'group': ['commongroup2']}, 'sn': (u'User',),
            'nsaccountlock': True}
        assert users[u'other.user'].data_repo == {
            'email': u'other.user@devgdc.com', 'firstName': u'Other',
            'lastName': u'User', 'memberOf': {'group': ['commongroup2']},
            'disabled': True}

        log.check(
            ('OktaLoader', 'INFO', 'Loading users from Okta'),
            ('OktaLoader', 'DEBUG',
             u'User some.user is ACTIVE in Okta, setting as active user'),
            ('OktaLoader', 'DEBUG',
             u'User other.user is SUSPENDED in Okta, setting as disabled'),
            ('OktaLoader', 'WARNING',
             u'User different.user@otherdomain.com does not '
             u'match UID regex "(.+)@devgdc.com", skipping'),
            ('OktaLoader', 'DEBUG',
             u'User terminated.user is DEPROVISIONED in Okta, not creating'),
            ('OktaLoader', 'DEBUG', StringComparison(
                "Users loaded from Okta: .+")),
            ('OktaLoader', 'INFO', '2 users loaded from Okta'))

    def test_load_groups(self):
        self.loader._get_okta_api_pages = mock.Mock()
        with open(os.path.join(testpath, 'okta/groups.json')) as resp_groups_fh:
            resp_groups = json.load(resp_groups_fh)
            self.loader._get_okta_api_pages.return_value = resp_groups

        groups = self.loader.load_groups()
        assert set(groups) == {'commongroup1', 'commongroup2'}

    def test_get_okta_api_pages(self):
        okta_mock = requests_mock.mock()
        okta_url = 'https://testoktaorg.okta.com/v1/tests'
        okta_url2 = 'https://testoktaorg.okta.com/v1/tests/page2'
        resp1 = [{'part': 'one'}]
        resp2 = [{'part': 'two'}]
        okta_mock.get(okta_url, json=resp1, headers={
            'link': '<%s>; rel="next"' % okta_url2})
        okta_mock.get(okta_url2, json=resp2)
        with okta_mock:
            assert self.loader._get_okta_api_pages(okta_url) == [
                {u'part': u'one'}, {u'part': u'two'}]

    def test_user_groups(self):
        okta_mock = requests_mock.mock()
        okta_url = 'https://testoktaorg.okta.com/api/v1/users/userid123/groups'

        with open(os.path.join(testpath, 'okta/groups.json')) as ug_fh:
            okta_mock.get(okta_url, text=ug_fh.read())

        with okta_mock:
            user = {'id': 'userid123', 'profile': {'login': 'user1'}}
            assert list(self.loader._user_groups(user)) == [
                u'oktagroup1', u'oktagroup2', u'commongroup1', u'commongroup2']

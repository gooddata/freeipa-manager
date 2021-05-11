#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2021, GoodData Corporation. All rights reserved.
"""
FreeIPA Manager - Okta user loading module

Module for loading user configuration from Okta account.
"""

import re
import requests

from core import FreeIPAManagerCore
from errors import OktaError
from entities import FreeIPAOktaUser
from utils import check_ignored


class OktaLoader(FreeIPAManagerCore):
    """
    Responsible for loading users from Okta.
    :attr dict users: Structure of users loaded from Okta
    """
    def __init__(self, settings, groups):
        """
        :param dict settings: parsed contents of the settings file
        :param list(str) groups: current groups defined for FreeIPA
        """
        super(OktaLoader, self).__init__()
        self.ignored = {'user': settings['okta'].get('ignore', [])}

        self.ipa_groups = set(groups)

        self.settings = settings
        okta_auth = self.settings['okta']['auth']

        self.okta_org = okta_auth['org']
        self.okta_token = self._load_okta_token(okta_auth['token_path'])
        self.okta_url = 'https://%s.okta.com/api/v1' % self.okta_org

        self._setup_okta_session()

    def _load_okta_token(self, path):
        with open(path) as tokenfile:
            return tokenfile.read().strip()

    def _setup_okta_session(self):
        self.session = requests.Session()
        self.session.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'SSWS %s' % self.okta_token
        }

    def load(self):
        """
        Parse Okta users and attributes.
        """
        self.lg.info('Loading users from Okta')
        users = dict()
        uid_regex = self.settings['okta']['user_id_regex']
        for user in self._get_okta_api_pages('%s/users' % self.okta_url):
            # parse UID from Okta
            uid_raw = user['profile']['login']
            if uid_regex:
                try:
                    uid = re.match(uid_regex, uid_raw).group(1)
                except AttributeError:
                    self.lg.warning(
                        'User %s does not match UID regex "%s", skipping',
                        uid_raw, uid_regex)
                    continue
            else:
                uid = uid_raw

            # check if ignored
            if check_ignored(FreeIPAOktaUser, uid, self.ignored):
                self.lg.info('Not creating ignored Okta user %s', uid)
                continue

            user_config = dict()

            # handle Okta user status
            status = user['status']
            if status in ('STAGED', 'DEPROVISIONED'):
                self.lg.debug('User %s is %s in Okta, not creating',
                              uid, status)
                # shouldn't be in FreeIPA at all
                continue
            elif status == 'SUSPENDED':
                self.lg.debug('User %s is %s in Okta, setting as disabled',
                              uid, status)
                # should be disabled
                user_config['disabled'] = True
            elif status in ('PROVISIONED', 'ACTIVE',
                            'PASSWORD_EXPIRED', 'LOCKED_OUT', 'RECOVERY'):
                self.lg.debug('User %s is %s in Okta, creating as active user',
                              uid, status)
                user_config['disabled'] = False

            for attr in self.settings['okta']['attributes']:
                if attr in user['profile']:
                    user_config[attr] = user['profile'][attr]
            groups = set(self._user_groups(user)).intersection(self.ipa_groups)
            if groups:
                user_config['memberOf'] = {'group': list(groups)}

            users[uid] = FreeIPAOktaUser(uid, user_config)
        self.lg.debug('Users loaded from Okta: %s', users.keys())
        self.lg.info('%d users loaded from Okta', len(users))
        return users

    def load_groups(self):
        okta_groups = [group['profile']['name'] for group in
                       self._get_okta_api_pages('%s/groups' % self.okta_url)]
        # only take groups that are both in Okta & IPA
        filtered_groups = list(set(okta_groups).intersection(self.ipa_groups))
        self.lg.debug('Groups loaded from Okta: %s', filtered_groups)
        self.lg.info('%d groups loaded from Okta', len(filtered_groups))
        return filtered_groups

    def _get_okta_api_pages(self, url):
        self.lg.debug('Getting Okta API response from %s', url)
        resp = self.session.get(url)
        if not resp.ok:
            raise OktaError('Error reading Okta API: %s', resp.text)
        results = resp.json()
        # handle pagination:
        if resp.links.get('next'):
            results.extend(self._get_okta_api_pages(resp.links['next']['url']))
        return results

    def _user_groups(self, user):
        self.lg.debug('Reading user %s (%s) Okta groups',
                      user['profile']['login'], user['id'])
        try:
            resp = self._get_okta_api_pages(
                '%s/users/%s/groups' % (self.okta_url, user['id']))
        except OktaError as e:
            raise OktaError('Error getting user %s groups: %s',
                            user['profile']['login'], e)
        return (gr['profile']['name'] for gr in resp)

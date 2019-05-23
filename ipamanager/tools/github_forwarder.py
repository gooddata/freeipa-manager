#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.

"""
FreeIPA Manager - GitHub forwarding tool

Tool for committing changes pulled from FreeIPA
and forwarding them to a GitHub repository via a pull request.
"""

import argparse
import json
import logging
import os
import re
import requests
import sh
import socket
import time

from ipamanager.errors import ManagerError
from ipamanager.tools.core import FreeIPAManagerToolCore


class GitHubForwarder(FreeIPAManagerToolCore):
    """
    Responsible for updating FreeIPA server with changed configuration.
    """
    def __init__(self, args=None):
        """
        Create a GitHub forwarder object.
        """
        self._parse_args(args)
        self.name = socket.getfqdn().replace('.int.', '.')
        self.msg = 'Entity dump from %s' % self.name
        # configure the repo path to be used for all git command calls
        self.git = sh.git.bake(_cwd=self.args.path)
        self.changes = False
        super(GitHubForwarder, self).__init__(self.args.loglevel)

    def run(self):
        """
        Run forwarding action based on arguments.
        :rtype: NoneType
        """
        self.lg.debug('Running the GitHubForwarder plugin')
        if self.args.commit:
            self._commit()
        elif self.args.pull_request:
            self._commit()
            self._create_pull_request()

    def _commit(self):
        """
        Checkout the defined branch and create a commit
        from changes in given config path.
        The flag `self.changes` is switched to True
        if there were changes to commit.
        :rtype: None
        :raises ManagerError: when checkout/add/commit fails
        """
        commit_msg = '%s at %s' % (
            self.msg, time.strftime('%d %h %Y %H:%M:%S'))
        self.lg.debug('Using commit message: %s', commit_msg)
        try:
            self.git.checkout(['-B', self.args.branch])
            self.git.add(['-A', '.'])
            self.git.commit(['-m', commit_msg])
        except sh.ErrorReturnCode_1 as e:
            if re.search('nothing to commit', e.stdout):
                self.lg.info('No changes, nothing to commit')
                return
            else:
                err = '; '.join(i for i in [e.stdout, e.stderr] if i)
                raise ManagerError('Committing failed: %s' % err)
        except Exception as e:
            raise ManagerError('Committing failed: %s' % e)
        self.changes = True
        self.lg.info('Committed successfully')

    def _push(self):
        """
        Push the commited change to given remote branch.
        NOTE: The remote name used is identical to GitHub user name supplied.
              The remote has to be pre-configured in the repo (e.g. by Puppet).
        :rtype: NoneType
        :raises ManagerError: when pushing fails (bad credentials etc.)
        """
        try:
            self.git.push([self.args.user, self.args.branch, '-f'])
        except sh.ErrorReturnCode as e:
            raise ManagerError('Pushing failed: %s' % e.stderr)
        self.lg.debug('Pushed to %s/%s successfully',
                      self.args.user, self.args.branch)

    def _generate_branch_name(self):
        """
        Generate branch name from IPA identification (which can be environment
        it is in - prod/int - or hostname as a fallback) and timestamp.
        :returns: branch name to use
        :rtype: str
        """
        return 'freeipa-%s' % os.getenv('EC2DATA_ENVIRONMENT', 'dev')

    def _make_request(self):
        """
        Make a POST request to create a pull request in the given GitHub repo.
        :returns: response to the made request
        :rtype: requests.models.Response
        """
        url = 'https://api.github.com/repos/%s/%s/pulls' % (
            self.args.owner, self.args.repo)
        headers = {'Authorization': 'token %s' % self.args.token}
        data = {
            'title': self.msg,
            'head': '%s:%s' % (self.args.user, self.args.branch),
            'base': self.args.base,
            'body': self.msg
        }
        return requests.post(url, headers=headers, data=json.dumps(data))

    def _parse_github_error(self, parsed):
        """
        Parse error message returned from GitHub. A separate method is useful
        because GitHub error responses are nested in specific ways.
        :param dict parsed: decoded JSON from GitHub API response
        :returns: composition of parsed error messages
        :rtype: str
        """
        msg = parsed['message']
        err_details = []
        for err in parsed.get('errors', []):
            if 'message' in err:
                err_details.append(err['message'])
            elif 'field' in err and 'code' in err:
                err_details.append('%s %s' % (err['field'], err['code']))
            else:
                err_details.append(str(err))
        if err_details:
            return '%s (%s)' % (msg, '; '.join(err_details))
        return msg

    def _create_pull_request(self):
        """
        Create a GitHub pull request with pulled changes. As pull request head,
        the branch supplied/generated during forwarder initialization is used.
        Pushing & PR creation is executed only if `self.changes` flag
        was set to True by the `_commit` method (i.e. there is a new commit).
        :rtype: None
        :raises ManagerError: if PR creation fails
        """
        if not self.changes:
            self.lg.info('Not creating PR because there were no changes')
            return
        self._push()
        response = self._make_request()
        parsed = response.json()
        if response.ok:
            url = parsed['html_url']
            self.lg.info('Pull request %s created successfully' % url)
        else:
            err = self._parse_github_error(parsed)
            if 'A pull request already exists' in err:
                self.lg.info('PR already exists, not creating another one.')
            else:
                raise ManagerError('Creating PR failed: %s' % err)

    def _parse_args(self, args=None):
        parser = argparse.ArgumentParser(description='GitHubForwarder')
        parser.add_argument('path', help='Config repository path')
        parser.add_argument('-b', '--branch', help='Branch to commit to',
                            default=self._generate_branch_name())
        parser.add_argument('-B', '--base', default='master',
                            help='PR base branch')
        parser.add_argument('-o', '--owner', default='gooddata',
                            help='GitHub repository owner')
        parser.add_argument('-r', '--repo', default='freeipa-manager-config',
                            help='GitHub repository name')
        parser.add_argument('-t', '--token', help='GitHub API token')
        parser.add_argument('-u', '--user', default='billie-jean',
                            help='GitHub user/fork remote name')
        actions = parser.add_mutually_exclusive_group()
        actions.add_argument('-c', '--commit', action='store_true',
                             help='Create a commit')
        actions.add_argument('-p', '--pull-request', action='store_true',
                             help='Create a pull request')
        parser_verbose = parser.add_mutually_exclusive_group()
        parser_verbose.set_defaults(loglevel=logging.WARNING)
        parser_verbose.add_argument(
            '-v', '--verbose', action='store_const',
            dest='loglevel', const=logging.INFO, help='Verbose mode')
        parser_verbose.add_argument(
            '-d', '--debug', action='store_const',
            dest='loglevel', const=logging.DEBUG, help='Debug mode')
        self.args = parser.parse_args(args)


def main():
    GitHubForwarder().run()


if __name__ == '__main__':
    main()

"""
GoodData FreeIPA tooling
GitHub forwarding tool

Tool for committing changes pulled from FreeIPA
and forwarding them to a GitHub repository via a pull request.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import json
import os
import re
import requests
import sh
import socket
import time

from core import FreeIPAManagerCore
from errors import ManagerError


class GitHubForwarder(FreeIPAManagerCore):
    """
    Responsible for updating FreeIPA server with changed configuration.
    """
    def __init__(self, config_path, base,
                 branch=None, timestamp=time.strftime('%Y-%m-%dT%H-%M-%S')):
        """
        Create a GitHub forwarder object.
        :param str config_path: path to configuration repository
        :param str base: base branch to use (e.g., master)
        :param str branch: Git branch to use (generated if not supplied)
        :param str timestamp: commit message timestamp (default: current time)
        """
        super(GitHubForwarder, self).__init__()
        self.name = socket.getfqdn().replace('.int.', '.')
        self.timestamp = timestamp
        self.base = base
        self.branch = branch or self._generate_branch_name()
        self.path = config_path
        # configure the repo path to be used for all git command calls
        self.git = sh.git.bake(_cwd=self.path)
        self.changes = False
        self.lg.debug('Using name %s, timestamp %s, branch %s, path %s',
                      self.name, self.timestamp, self.branch, self.path)

    def checkout_base(self):
        """
        Checkout the `self.base` branch (before pulling).
        :rtype: None
        :raises ManagerError: when checkout
        """
        self.lg.debug('Checking out branch %s in %s', self.base, self.path)
        try:
            self.git.checkout([self.base])
        except sh.ErrorReturnCode as e:
            raise ManagerError('Checkout failed: %s' % e.stderr)
        self.lg.info('Repo %s branch %s checked out', self.path, self.base)

    def commit(self):
        """
        Checkout the defined branch and create a commit
        from changes in given config path.
        The flag `self.changes` is switched to True
        if there were changes to commit.
        :rtype: None
        :raises ManagerError: when checkout/add/commit fails
        """
        self.msg = '%s dump at %s' % (self.name, self.timestamp)
        self.lg.debug('Using commit message: %s', self.msg)
        try:
            self.git.checkout(['-B', self.branch])
            self.git.add(['.'])
            self.git.commit(['-m', self.msg])
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

    def _push(self, remote):
        """
        Push the commited change to given remote branch.
        NOTE: the remote has to be pre-configured in the repo (e.g., by Puppet)
        :param str remote: Git repository remote name
        :rtype: None
        :raises ManagerError: when pushing fails (bad credentials etc.)
        """
        try:
            self.git.push([remote, self.branch, '-f'])
        except sh.ErrorReturnCode as e:
            raise ManagerError('Pushing failed: %s' % e.stderr)
        self.lg.debug('Pushed to %s/%s successfully', remote, self.branch)

    def _generate_branch_name(self):
        """
        Generate branch name from IPA identification (which can be environment
        it is in - prod/int - or hostname as a fallback) and timestamp.
        :returns: branch name to use
        :rtype str:
        """
        ipa_identification = os.getenv('EC2DATA_ENVIRONMENT', self.name)
        return '%s-%s' % (ipa_identification, self.timestamp)

    def _make_request(self, owner, repo, fork, token):
        """
        Make a POST request to create a pull request in the given GitHub repo.
        :param str owner: GitHub repository owner (usually gooddata)
        :param str repo: GitHub repository name
        :param str fork: name of GitHub user from whose fork to create PR
                         (should be equivalent to the relevant Git remote name)
        :param str token: GitHub API token with which to authorize request
        :returns: response to the made request
        :rtype: requests.models.Response
        """
        url = 'https://api.github.com/repos/%s/%s/pulls' % (owner, repo)
        headers = {'Authorization': 'token %s' % token}
        data = {
            'title': self.msg,
            'head': '%s:%s' % (fork, self.branch),
            'base': self.base
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

    def create_pull_request(self, owner, repo, remote, token):
        """
        Create a GitHub pull request with pulled changes. As pull request head,
        the branch supplied/generated during forwarder initialization is used.
        Pushing & PR creation is executed only if `self.changes` flag
        was set to True by the `commit` method (i.e. there is a new commit).
        :param str owner: GitHub repository owner (usually gooddata)
        :param str repo: GitHub repository name
        :param str remote: GitHub remote of fork from which to create PR
                           (usually equivalent to the user that creates the PR)
        :param str token: GitHub API token with which to authorize request
        :rtype: None
        :raises ManagerError: if PR creation fails
        """
        if not self.changes:
            self.lg.info('Not creating PR because there were no changes')
            return
        self._push(remote)
        response = self._make_request(owner, repo, remote, token)
        parsed = response.json()
        if response.ok:
            url = parsed['html_url']
            self.lg.info('Pull request %s created successfully' % url)
        else:
            err = self._parse_github_error(parsed)
            raise ManagerError('Creating PR failed: %s' % err)

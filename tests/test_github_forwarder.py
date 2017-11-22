import json
import logging
import mock
import os
import pytest
import requests_mock
import sh
from testfixtures import log_capture

from _utils import _import
tool = _import('ipamanager', 'github_forwarder')
modulename = 'ipamanager.github_forwarder'
responses = os.path.join(os.path.dirname(__file__), 'api-responses')


class TestGitHubForwarder(object):
    def setup_method(self, method):
        self.ts = '2017-12-29T23-59-59'
        self.gh = 'https://api.github.com/repos'
        with mock.patch('%s.socket.getfqdn' % modulename, lambda: 'ipa.dummy'):
            self.forwarder = tool.GitHubForwarder(
                'config', 'master', None, self.ts)
        self.forwarder.name = 'ipa.dummy'
        self.forwarder.msg = 'Awesome pull request'
        if method.func_name.startswith('test_pull_request_'):
            method_end = method.func_name.replace('test_pull_request_', '')
            self.forwarder._push = mock.Mock()
            self.forwarder.changes = True
            self.gh_mock = requests_mock.mock()
            try:
                self.resp = self._load_resp('create_pr_%s' % method_end)
                self.gh_mock.post(
                    '%s/gooddata/freeipa-manager-config/pulls' % self.gh,
                    text=self.resp, status_code=422)
            except IOError:
                pass

    def _load_resp(self, name):
        with open('%s/%s.json' % (responses, name), 'r') as f:
            return f.read()

    @log_capture('GitHubForwarder', level=logging.DEBUG)
    def test_checkout_base(self, captured_log):
        self.forwarder.git = mock.Mock()
        self.forwarder.checkout_base()
        captured_log.check(('GitHubForwarder', 'DEBUG',
                            'Checking out branch master in config'),
                           ('GitHubForwarder', 'INFO',
                            'Repo config branch master checked out'))

    def test_checkout_base_error(self):
        err = "pathspec 'branch1' did not match any file(s) known to git."
        self.forwarder.git = mock.Mock()
        self.forwarder.git.checkout.side_effect = sh.ErrorReturnCode_1(
            '/usr/bin/git checkout branch1', '', 'error: %s' % err, False)
        with pytest.raises(tool.ManagerError) as exc:
            self.forwarder.checkout_base()
        assert exc.value[0] == 'Checkout failed: error: %s' % err

    def test_commit(self):
        self.forwarder.git = mock.Mock()
        with mock.patch('%s.socket.getfqdn' % modulename, lambda: 'ipa.dummy'):
            self.forwarder.commit()
            self.forwarder.git.checkout.assert_called_with(
                ['-B', 'ipa.dummy-2017-12-29T23-59-59'])
            self.forwarder.git.add.assert_called_with(['.'])
            self.forwarder.git.commit.assert_called_with(
                ['-m', 'ipa.dummy dump at 2017-12-29T23-59-59'])

    @log_capture('GitHubForwarder', level=logging.INFO)
    def test_commit_no_changes(self, captured_log):
        forwarder = tool.GitHubForwarder('wrong_path', self.ts)
        forwarder.git = mock.Mock()
        cmd = "/usr/bin/git commit -m 'ipa.dummy dump at 2017-12-29T23-59-59'"
        stdout = ("On branch master\nYour branch is up-to-date with "
                  "'origin/master'.\nnothing to commit, working tree clean\n")
        forwarder.git.commit.side_effect = sh.ErrorReturnCode_1(
            cmd, stdout, '', False)
        with mock.patch('%s.socket.getfqdn' % modulename, lambda: 'ipa.dummy'):
            forwarder.commit()
        captured_log.check(('GitHubForwarder', 'INFO',
                            'No changes, nothing to commit'))

    def test_commit_error(self):
        forwarder = tool.GitHubForwarder('config_path', self.ts)
        forwarder.git = mock.Mock()
        forwarder.git.commit.side_effect = sh.ErrorReturnCode_1(
            "/usr/bin/git commit -am 'msg'", '', 'an error occured', False)
        with pytest.raises(tool.ManagerError) as exc:
            forwarder.commit()
        assert exc.value[0] == 'Committing failed: an error occured'

    def test_commit_no_repo(self):
        forwarder = tool.GitHubForwarder('wrong_path', self.ts)
        forwarder.git = mock.Mock()
        err_msg = "[Errno 2] No such file or directory: 'wrong_path'"
        forwarder.git.commit.side_effect = OSError(err_msg)
        with pytest.raises(tool.ManagerError) as exc:
            forwarder.commit()
        assert exc.value[0] == "Committing failed: %s" % err_msg

    def test_push(self):
        forwarder = tool.GitHubForwarder(
            'config_path', 'master', 'branch1', self.ts)
        forwarder.git = mock.Mock()
        forwarder._push('yenkins')
        forwarder.git.push.assert_called_with(['yenkins', 'branch1', '-f'])

    def test_push_error(self):
        forwarder = tool.GitHubForwarder('config_path', None, self.ts)
        forwarder.git = mock.Mock()
        cmd = '/usr/bin/git push yenkins some-branch'
        stderr = ("error: src refspec master does not match any.\n"
                  "error: failed to push some refs to "
                  "'ssh://git@github.com/gooddata/gdc-ipa-utils.git'\n")
        forwarder.git.push.side_effect = sh.ErrorReturnCode_1(
            cmd, '', stderr, False)
        with pytest.raises(tool.ManagerError) as exc:
            forwarder._push('yenkins')
        assert exc.value[0] == (
            "Pushing failed: error: src refspec master does not match any.\n"
            "error: failed to push some refs to "
            "'ssh://git@github.com/gooddata/gdc-ipa-utils.git'\n")

    @mock.patch.dict(os.environ, {'EC2DATA_ENVIRONMENT': 'prod'})
    def test_generate_branch_name(self):
        forwarder = tool.GitHubForwarder('config_path', 'base', None, self.ts)
        assert forwarder._generate_branch_name() == 'prod-2017-12-29T23-59-59'

    @mock.patch.dict(os.environ, {'EC2DATA_ENVIRONMENT': 'int'})
    def test_generate_branch_name_no_timestamp(self):
        forwarder = tool.GitHubForwarder('config_path', 'master')
        forwarder.timestamp = '2018-01-01T01-02-03'
        assert forwarder._generate_branch_name() == 'int-2018-01-01T01-02-03'

    @mock.patch('%s.requests' % modulename)
    def test_make_request(self, mock_requests):
        def _mock_dump(x):
            return str(sorted(x.items()))
        with mock.patch('%s.json.dumps' % modulename, _mock_dump):
            self.forwarder._make_request(
                'gooddata', 'config-repo', 'yenkins', 'dummy-token')
        dumped_data = (
            "[('base', 'master'), ('head', 'yenkins:ipa.dummy-2017-12-29"
            "T23-59-59'), ('title', 'Awesome pull request')]")
        mock_requests.post.assert_called_with(
            'https://api.github.com/repos/gooddata/config-repo/pulls',
            data=dumped_data, headers={'Authorization': 'token dummy-token'})

    def test_parse_github_error_messageonly(self):
        data = {'message': 'Bad Credentials'}
        assert self.forwarder._parse_github_error(data) == 'Bad Credentials'

    def test_parse_github_error_errorlist_one(self):
        data = json.loads(self._load_resp('create_pr_already_exists'))
        assert self.forwarder._parse_github_error(data) == (
            'Validation Failed (A pull request '
            'already exists for yenkins:same-branch.)')

    def test_parse_github_error_errorlist_several(self):
        data = {
            'message': 'Validation Failed',
            'errors': [{'message': 'some error'},
                       {'field': 'base', 'code': 'invalid'}]
        }
        assert self.forwarder._parse_github_error(data) == (
            'Validation Failed (some error; base invalid)')

    def test_parse_github_error_default(self):
        data = {
            'message': 'Error happened',
            'errors': [{'message': 'some error'},
                       {'help': 'More error info'}]
        }
        assert self.forwarder._parse_github_error(data) == (
            "Error happened (some error; {'help': 'More error info'})")

    @log_capture('GitHubForwarder', level=logging.INFO)
    def test_pull_request_no_changes(self, captured_log):
        self.forwarder.changes = False
        self.forwarder.create_pull_request(
            'gooddata', 'freeipa-manager-config', 'yenkins', 'dummy-token')
        self.forwarder._push.assert_not_called()
        captured_log.check(('GitHubForwarder', 'INFO',
                            'Not creating PR because there were no changes'))

    @log_capture('GitHubForwarder', level=logging.INFO)
    def test_pull_request_success(self, captured_log):
        with requests_mock.mock() as gh_mock:
            gh_mock.post('%s/gooddata/freeipa-manager-config/pulls' % self.gh,
                         text=self._load_resp('create_pr_success'))
            self.forwarder.create_pull_request(
                'gooddata', 'freeipa-manager-config', 'yenkins', 'dummy-token')
            self.forwarder._push.assert_called_with('yenkins')
        captured_log.check(('GitHubForwarder', 'INFO',
                            ('Pull request https://github.com/gooddata/freeipa'
                             '-manager-config/pull/42 created successfully')))

    def test_pull_request_already_exists(self):
        with self.gh_mock:
            with pytest.raises(tool.ManagerError) as exc:
                self.forwarder.create_pull_request(
                    'gooddata', 'freeipa-manager-config',
                    'yenkins', 'dummy-token')
        assert exc.value[0] == (
            'Creating PR failed: Validation Failed '
            '(A pull request already exists for yenkins:same-branch.)')

    def test_pull_request_bad_credentials(self):
        with self.gh_mock:
            with pytest.raises(tool.ManagerError) as exc:
                self.forwarder.create_pull_request(
                    'gooddata', 'freeipa-manager-config',
                    'yenkins', 'dummy-token')
        assert exc.value[0] == 'Creating PR failed: Bad credentials'

    def test_pull_request_base_invalid(self):
        with self.gh_mock:
            with pytest.raises(tool.ManagerError) as exc:
                self.forwarder.create_pull_request(
                    'gooddata', 'freeipa-manager-config',
                    'yenkins', 'dummy-token')
        assert exc.value[0] == (
            'Creating PR failed: Validation Failed (base invalid)')

    def test_pull_request_head_invalid(self):
        with self.gh_mock:
            with pytest.raises(tool.ManagerError) as exc:
                self.forwarder.create_pull_request(
                    'gooddata', 'freeipa-manager-config',
                    'yenkins', 'dummy-token')
        assert exc.value[0] == (
            'Creating PR failed: Validation Failed (head invalid)')

    def test_pull_request_no_commits(self):
        with self.gh_mock:
            with pytest.raises(tool.ManagerError) as exc:
                self.forwarder.create_pull_request(
                    'gooddata', 'freeipa-manager-config',
                    'yenkins', 'dummy-token')
        assert exc.value[0] == (
            'Creating PR failed: Validation Failed '
            '(No commits between gooddata:master and yenkins:some-branch)')

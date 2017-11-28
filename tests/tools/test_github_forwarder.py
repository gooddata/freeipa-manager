import json
import logging
import mock
import os
import pytest
import requests_mock
import sys
import sh
from testfixtures import log_capture

testdir = os.path.dirname(__file__)
sys.path.insert(0, testdir.replace('/tests/tools', ''))
import ipamanager.tools.github_forwarder as tool

modulename = 'ipamanager.tools.github_forwarder'
responses = os.path.join(testdir, 'api-responses')


class TestGitHubForwarder(object):
    def setup_method(self, method):
        self.ts = '2017-12-29T23-59-59'
        self.gh = 'https://api.github.com/repos'
        with mock.patch('%s.socket.getfqdn' % modulename, lambda: 'ipa.dummy'):
            with mock.patch('time.strftime', lambda _: self.ts):
                with mock.patch('sys.argv', ['ipamanager-pr', 'dump_repo']):
                    self.forwarder = tool.GitHubForwarder()
        self.forwarder.args.repo = 'config-repo'
        self.forwarder.name = 'ipa.dummy'
        self.forwarder.msg = 'Awesome pull request'
        if method.func_name.startswith('test_pull_request_'):
            method_end = method.func_name.replace('test_pull_request_', '')
            self.forwarder._push = mock.Mock()
            self.forwarder.changes = True
            self.gh_mock = requests_mock.mock()
            try:
                self.resp = self._load_resp('create_pr_%s' % method_end)
                self.gh_mock.post('%s/gooddata/config-repo/pulls' % self.gh,
                                  text=self.resp, status_code=422)
            except IOError:
                pass

    def _load_resp(self, name):
        with open('%s/%s.json' % (responses, name), 'r') as f:
            return f.read()

    def test_commit(self):
        self.forwarder.git = mock.Mock()
        with mock.patch('%s.socket.getfqdn' % modulename, lambda: 'ipa.dummy'):
            self.forwarder._commit()
            self.forwarder.git.checkout.assert_called_with(
                ['-B', 'ipa.dummy-2017-12-29T23-59-59'])
            self.forwarder.git.add.assert_called_with(['.'])
            self.forwarder.git.commit.assert_called_with(
                ['-m', 'ipa.dummy dump at 2017-12-29T23-59-59'])

    @log_capture('GitHubForwarder', level=logging.INFO)
    def test_commit_no_changes(self, captured_log):
        self.forwarder.git = mock.Mock()
        cmd = "/usr/bin/git commit -m 'ipa.dummy dump at 2017-12-29T23-59-59'"
        stdout = ("On branch master\nYour branch is up-to-date with "
                  "'origin/master'.\nnothing to commit, working tree clean\n")
        self.forwarder.git.commit.side_effect = sh.ErrorReturnCode_1(
            cmd, stdout, '', False)
        with mock.patch('%s.socket.getfqdn' % modulename, lambda: 'ipa.dummy'):
            self.forwarder._commit()
        captured_log.check(('GitHubForwarder', 'INFO',
                            'No changes, nothing to commit'))

    def test_commit_error(self):
        self.forwarder.git = mock.Mock()
        self.forwarder.git.commit.side_effect = sh.ErrorReturnCode_1(
            "/usr/bin/git commit -am 'msg'", '', 'an error occured', False)
        with pytest.raises(tool.ManagerError) as exc:
            self.forwarder._commit()
        assert exc.value[0] == 'Committing failed: an error occured'

    def test_commit_no_repo(self):
        self.forwarder.git = mock.Mock()
        self.forwarder.args.path = 'wrong_path'
        err_msg = "[Errno 2] No such file or directory: 'wrong_path'"
        self.forwarder.git.commit.side_effect = OSError(err_msg)
        with pytest.raises(tool.ManagerError) as exc:
            self.forwarder._commit()
        assert exc.value[0] == "Committing failed: %s" % err_msg

    def test_push(self):
        self.forwarder.git = mock.Mock()
        self.forwarder.args.branch = 'branch'
        self.forwarder._push()
        self.forwarder.git.push.assert_called_with(['yenkins', 'branch', '-f'])

    def test_push_error(self):
        self.forwarder.git = mock.Mock()
        cmd = '/usr/bin/git push yenkins some-branch'
        stderr = ("error: src refspec master does not match any.\n"
                  "error: failed to push some refs to "
                  "'ssh://git@github.com/gooddata/gdc-ipa-utils.git'\n")
        self.forwarder.git.push.side_effect = sh.ErrorReturnCode_1(
            cmd, '', stderr, False)
        with pytest.raises(tool.ManagerError) as exc:
            self.forwarder._push()
        assert exc.value[0] == (
            "Pushing failed: error: src refspec master does not match any.\n"
            "error: failed to push some refs to "
            "'ssh://git@github.com/gooddata/gdc-ipa-utils.git'\n")

    @mock.patch.dict(os.environ, {'EC2DATA_ENVIRONMENT': 'int'})
    def test_generate_branch_name(self):
        self.forwarder.timestamp = '2018-01-01T01-02-03'
        assert self.forwarder._generate_branch_name() == (
            'int-2018-01-01T01-02-03')

    @mock.patch('%s.requests' % modulename)
    def test_make_request(self, mock_requests):
        def _mock_dump(x):
            return str(sorted(x.items()))
        with mock.patch('%s.json.dumps' % modulename, _mock_dump):
            self.forwarder._make_request()
        dumped_data = (
            "[('base', 'master'), ('head', 'yenkins:ipa.dummy-2017-12-29"
            "T23-59-59'), ('title', 'Awesome pull request')]")
        mock_requests.post.assert_called_with(
            'https://api.github.com/repos/gooddata/config-repo/pulls',
            data=dumped_data, headers={'Authorization': 'token None'})

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
        self.forwarder._create_pull_request()
        self.forwarder._push.assert_not_called()
        captured_log.check(('GitHubForwarder', 'INFO',
                            'Not creating PR because there were no changes'))

    @log_capture('GitHubForwarder', level=logging.INFO)
    def test_pull_request_success(self, captured_log):
        self.forwarder.args.repo = 'config-repo'
        with requests_mock.mock() as gh_mock:
            gh_mock.post('%s/gooddata/config-repo/pulls' % self.gh,
                         text=self._load_resp('create_pr_success'))
            self.forwarder._create_pull_request()
            self.forwarder._push.assert_called_with()
        captured_log.check(('GitHubForwarder', 'INFO',
                            ('Pull request https://github.com/gooddata/config-'
                             'repo/pull/42 created successfully')))

    def test_pull_request_already_exists(self):
        with self.gh_mock:
            with pytest.raises(tool.ManagerError) as exc:
                self.forwarder._create_pull_request()
        assert exc.value[0] == (
            'Creating PR failed: Validation Failed '
            '(A pull request already exists for yenkins:same-branch.)')

    def test_pull_request_bad_credentials(self):
        with self.gh_mock:
            with pytest.raises(tool.ManagerError) as exc:
                self.forwarder._create_pull_request()
        assert exc.value[0] == 'Creating PR failed: Bad credentials'

    def test_pull_request_base_invalid(self):
        with self.gh_mock:
            with pytest.raises(tool.ManagerError) as exc:
                self.forwarder._create_pull_request()
        assert exc.value[0] == (
            'Creating PR failed: Validation Failed (base invalid)')

    def test_pull_request_head_invalid(self):
        with self.gh_mock:
            with pytest.raises(tool.ManagerError) as exc:
                self.forwarder._create_pull_request()
        assert exc.value[0] == (
            'Creating PR failed: Validation Failed (head invalid)')

    def test_pull_request_no_commits(self):
        with self.gh_mock:
            with pytest.raises(tool.ManagerError) as exc:
                self.forwarder._create_pull_request()
        assert exc.value[0] == (
            'Creating PR failed: Validation Failed '
            '(No commits between gooddata:master and yenkins:some-branch)')

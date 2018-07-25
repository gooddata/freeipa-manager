"""
GoodData FreeIPA tooling

Main entry point of the tooling, responsible for delegating the tasks.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import sys
import voluptuous
import yaml

import utils
from core import FreeIPAManagerCore
from config_loader import ConfigLoader
from difference import FreeIPADifference
from errors import ManagerError
from integrity_checker import IntegrityChecker
from schemas import schema_settings


class FreeIPAManager(FreeIPAManagerCore):
    """
    Main runnable class responsible for coordinating module functionality.
    """
    def __init__(self):
        super(FreeIPAManager, self).__init__()
        self.args = utils.parse_args()
        utils.init_logging(self.args.loglevel)
        self._load_settings()

    def run(self):
        """
        Execute the task selected by arguments (check config, upload etc).
        """
        try:
            {
                'check': self.check,
                'push': self.push,
                'pull': self.pull,
                'diff': self.diff
            }[self.args.action]()
        except ManagerError as e:
            self.lg.error(e)
            sys.exit(1)

    def check(self):
        """
        Load configurations from configuration repository at the given path.
        Run integrity check on the loaded configuration.
        :raises ConfigError: in case of configuration syntax errors
        :raises IntegrityError: in case of config entity integrity violations
        """
        self.config_loader = ConfigLoader(self.args.config, self.settings)
        self.entities = self.config_loader.load()
        self.integrity_checker = IntegrityChecker(self.entities, self.settings)
        self.integrity_checker.check()

    def push(self):
        """
        Run upload of configuration to FreeIPA via API.
        This can only be run locally on FreeIPA nodes.
        Arguments to the IpaConnector instance
        are passed from `self.args` in the `_api_connect` method.
        :raises ConfigError: in case of configuration syntax errors
        :raises IntegrityError: in case of config entity integrity violations
        :raises ManagerError: in case of API connection error or update error
        """
        self.check()
        from ipa_connector import IpaUploader
        utils.init_api_connection(self.args.loglevel)
        self.uploader = IpaUploader(
            self.settings, self.entities, self.args.threshold,
            self.args.force, self.args.deletion)
        self.uploader.push()

    def pull(self):
        """
        Run upload of configuration to FreeIPA via API.
        This can only be run locally on FreeIPA nodes.
        Arguments to the IpaConnector instance
        are passed from `self.args` in the `_api_connect` method.
        :raises ConfigError: in case of configuration syntax errors
        :raises IntegrityError: in case of config entity integrity violations
        :raises ManagerError: in case of API connection error or update error
        """
        self.check()
        from ipa_connector import IpaDownloader
        utils.init_api_connection(self.args.loglevel)
        self.downloader = IpaDownloader(
            self.settings, self.entities, self.args.config,
            self.args.dry_run, self.args.add_only)
        self.downloader.pull()

    def diff(self):
        """
        Makes set-like difference between 2 dirs. Arguments to the diff are
        passed from `self.args` in the `_api_connect` method.
        :raises IntegrityError: in case the difference is not empty
        """
        diff = FreeIPADifference(self.args.config, self.args.sub_path)
        diff.run()

    def _load_settings(self):
        """
        Load the settings file. The file contains integrity check settings,
        ignored entities configuration and other useful settings.
        """
        if not self.args.settings:
            raise ManagerError('No settings file configured')
        self.lg.debug('Loading settings file from %s', self.args.settings)
        try:
            with open(self.args.settings) as src:
                raw = src.read()
                utils.run_yamllint_check(raw)
                self.settings = yaml.safe_load(raw)
                # run validation of parsed YAML against schema
                voluptuous.Schema(schema_settings)(self.settings)
        except Exception as e:
            raise ManagerError('Error reading settings file: %s' % e)
        self.lg.debug('Settings parsed: %s', self.settings)


def main():
    manager = FreeIPAManager()
    manager.run()


if __name__ == '__main__':
    main()

"""
GoodData FreeIPA tooling
Configuration parsing tool

Tools for loading FreeIPA configuration
from a locally cloned config repo.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import glob
import os
import yaml
from yamllint.linter import run as yamllint_check
from yamllint.config import YamlLintConfig

from core import FreeIPAManagerCore
from entities import FreeIPAEntity
from errors import ConfigError, ManagerError
from utils import ENTITY_CLASSES


class ConfigLoader(FreeIPAManagerCore):
    """
    Responsible for loading configuration YAML files from the repository.
    :attr dict entities: storage of loaded entities, which are organized
                         in lists under entity class name keys.
    """
    def __init__(self, basepath, ignored_file):
        """
        :param str basepath: path to the cloned config repository
        :param str ignored_file: path to file with ignored entity list
        """
        super(ConfigLoader, self).__init__()
        self.basepath = basepath
        self.ignored_file = ignored_file
        self.entities = dict()
        self.yamllint_config = YamlLintConfig('extends: default')

    def load_ignored(self):
        """
        Parse list of entities that should be ignored during processing.
        """
        if not self.ignored_file:
            self.lg.debug('No ignored entities file configured.')
            return
        self.lg.debug('Loading ignored entity list from %s', self.ignored_file)
        try:
            with open(self.ignored_file) as ignored:
                data = yaml.safe_load(ignored)
        except (IOError, yaml.YAMLError) as e:
            raise ManagerError('Error opening ignored entities file: %s' % e)
        if not isinstance(data, dict):
            raise ManagerError('Ignored entities file error: must be a dict')
        for t, name_list in data.iteritems():
            if not isinstance(name_list, list):
                raise ManagerError(
                    'Ignored entities file error: values must be name lists')
            try:
                cls = FreeIPAEntity.get_entity_class(t)
                cls.ignored = [str(name) for name in name_list]
                self.lg.debug(
                    'Ignore list %s added to class %s', cls.ignored, t)
            except KeyError:
                raise ManagerError(
                    'Invalid type in ignored entities file: %s' % t)

    def load(self):
        """
        Parse FreeIPA entity configurations from the given paths.
        """
        self.load_ignored()
        self.lg.info('Checking local configuration at %s', self.basepath)
        paths = self._retrieve_paths()
        for entity_class in ENTITY_CLASSES:
            self.entities[entity_class.entity_name] = list()
            entity_paths = paths.get(entity_class.entity_name, [])
            if not entity_paths:
                continue
            self.lg.debug('Loading %s configs', entity_class.entity_name)
            errcount = 0
            for path in entity_paths:
                fname = os.path.relpath(path, self.basepath)
                self.lg.debug('Loading config from %s', fname)
                try:
                    with open(path, 'r') as confsource:
                        contents = confsource.read()
                    self._run_yamllint_check(contents, fname)
                    data = yaml.safe_load(contents)
                    self._parse(data, entity_class, path)
                except (IOError, ConfigError, yaml.YAMLError) as e:
                    self.lg.error('%s: %s', fname, e)
                    self.errs.append(fname)
                    errcount += 1
            self.lg.info(
                'Parsed %d %s%s', len(self.entities[entity_class.entity_name]),
                '%ss' % entity_class.entity_name,
                ' (%d errors encountered)' % errcount if errcount else '')
        if self.errs:
            raise ConfigError(
                'There have been errors in %d configuration files: [%s]' %
                (len(self.errs), ', '.join(sorted(self.errs))))

    def _run_yamllint_check(self, data, fname):
        """
        Run a yamllint check on parsed file contents
        to verify that the file syntax is correct.
        :param str data: contents of the configuration file to check
        :raises ConfigError: in case of yamllint errors
        """
        lint_errs = [err for err in yamllint_check(data, self.yamllint_config)]
        if lint_errs:
            raise ConfigError('yamllint errors: %s' % lint_errs)
        self.lg.debug('%s yamllint check passed successfully', fname)

    def _parse(self, data, entity_class, path):
        """
        Parse entity instances from loaded YAML dictionary.
        :param dict data: contents of loaded YAML configuration file
        :param FreeIPAEntity entity_class: entity class to create instances of
        :param str path: configuration file path
        """
        if not data or not isinstance(data, dict):
            raise ConfigError('Config must be a non-empty dictionary')
        parsed = []
        fname = os.path.relpath(path, self.basepath)
        for name, attrs in data.iteritems():
            self.lg.debug('Creating entity %s', name)
            if name in entity_class.ignored:
                self.lg.warning('Not creating ignored %s %s from %s',
                                entity_class.entity_name, name, fname)
                continue
            entity = entity_class(name, attrs, path)
            if entity in self.entities[entity_class.entity_name]:
                raise ConfigError('Duplicit definition of %s' % entity)
            parsed.append(entity)
        if len(parsed) > 1:
            raise ConfigError(
                'More than one entity parsed from %s (%d)'
                % (fname, len(parsed)))
        self.entities[entity_class.entity_name].extend(parsed)

    def _retrieve_paths(self):
        """
        Retrieve all available configuration YAML files from the repository.
        """
        filepaths = dict()
        for entity_class in ENTITY_CLASSES:
            folder = os.path.join(
                self.basepath, '%ss' % entity_class.entity_name)
            entity_filepaths = glob.glob('%s/*.yaml' % folder)
            self.lg.debug(
                'Retrieved %s config paths: [%s]',
                entity_class.entity_name, ', '.join(entity_filepaths))
            if not entity_filepaths:
                self.lg.warning('No %s files found', entity_class.entity_name)
                continue
            filepaths[entity_class.entity_name] = entity_filepaths
        return filepaths

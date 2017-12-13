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

from core import FreeIPAManagerCore
from errors import ConfigError
from utils import ENTITY_CLASSES, check_ignored, run_yamllint_check


class ConfigLoader(FreeIPAManagerCore):
    """
    Responsible for loading configuration YAML files from the repository.
    :attr dict entities: storage of loaded entities, which are organized
                         in nested dicts under entity type & entity name keys
    """
    def __init__(self, basepath, settings):
        """
        :param str basepath: path to the cloned config repository
        :param dict settings: parsed contents of the settings file
        """
        super(ConfigLoader, self).__init__()
        self.basepath = basepath
        self.ignored = settings.get('ignore', dict())
        self.entities = dict()

    def load(self):
        """
        Parse FreeIPA entity configurations from the given paths.
        """
        self.lg.info('Checking local configuration at %s', self.basepath)
        paths = self._retrieve_paths()
        for entity_class in ENTITY_CLASSES:
            self.entities[entity_class.entity_name] = dict()
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
                    run_yamllint_check(contents)
                    self.lg.debug('%s yamllint check passed', fname)
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
        return self.entities

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
            if check_ignored(entity_class, name, self.ignored):
                self.lg.info('Not creating ignored %s %s from %s',
                             entity_class.entity_name, name, fname)
                continue
            entity = entity_class(name, attrs, path)
            if name in self.entities[entity_class.entity_name]:
                raise ConfigError('Duplicit definition of %s' % repr(entity))
            parsed.append(entity)
        if len(parsed) > 1:
            raise ConfigError(
                'More than one entity parsed from %s (%d)'
                % (fname, len(parsed)))
        for entity in parsed:
            self.entities[entity_class.entity_name][entity.name] = entity

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
                self.lg.info('No %s files found', entity_class.entity_name)
                continue
            filepaths[entity_class.entity_name] = entity_filepaths
        return filepaths

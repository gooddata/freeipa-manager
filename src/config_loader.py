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
from utils import ENTITY_CLASSES


class ConfigLoader(FreeIPAManagerCore):
    """
    Responsible for loading configuration YAML files from the repository.
    :attr dict entities: storage of loaded entities, which are organized
                         in lists under entity class name keys.
    """
    def __init__(self, basepath):
        """
        :param str basepath: path to the cloned config repository
        """
        super(ConfigLoader, self).__init__()
        self.basepath = basepath
        self.entities = dict()

    def load(self):
        """
        Parse FreeIPA entity configurations from the given paths.
        """
        self.lg.info('Checking local configuration at %s', self.basepath)
        paths = self._retrieve_paths()
        for entity_class in ENTITY_CLASSES:
            entity_paths = paths.get(entity_class.entity_name, [])
            if not entity_paths:
                continue
            self.entities[entity_class.entity_name] = list()
            self.lg.debug('Loading %s configs', entity_class.entity_name)
            errcount = 0
            for path in entity_paths:
                fname = self._short_path(path)
                self.lg.debug('Loading config from %s', fname)
                try:
                    with open(path, 'r') as confsource:
                        data = yaml.safe_load(confsource)
                    self._parse(data, entity_class, fname)
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

    def _parse(self, data, entity_class, fname):
        """
        Parse entity instances from loaded YAML dictionary.
        :param dict data: contents of loaded YAML configuration file
        :param FreeIPAEntity entity_class: entity class to create instances of
        :param str fname: short configuration file path
        """
        if not data or not isinstance(data, dict):
            raise ConfigError('Config must be a non-empty dictionary')
        parsed = []
        for name, attrs in data.iteritems():
            self.lg.debug('Creating entity %s', name)
            entity = entity_class(name, attrs)
            if entity in self.entities[entity_class.entity_name]:
                raise ConfigError('Duplicit definition of %s' % entity)
            parsed.append(entity)
        if len(parsed) > 1:
            self.lg.warning(
                'More than one entity parsed from %s (%d)', fname, len(parsed))
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

    def _short_path(self, path):
        """
        Compose a shorter configuration file path for better log readability
        (relative to the repo path, e.g. users/name.yaml).
        """
        return os.path.join(
            os.path.basename(os.path.dirname(path)), os.path.basename(path))

"""
GoodData FreeIPA tooling
Configuration parsing tool

Tools for validating & parsing the FreeIPA
configuration for hosts, users & groups.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import glob
import os
import yaml

import config_parser as parsers
from core import FreeIPAManagerCore
from errors import ConfigError, ManagerError
from utils import ENTITY_TYPES


class EntityLoader(FreeIPAManagerCore):
    """
    Responsible for loading configuration YAML files from the repository.
    """
    def __init__(self, basepath):
        """
        :param str basepath: path to the cloned config repository
        """
        super(EntityLoader, self).__init__()
        self.basepath = basepath
        self.parsers = {
            'hostgroups': parsers.HostGroupConfigParser(),
            'users': parsers.UserConfigParser(),
            'usergroups': parsers.UserGroupConfigParser()
        }
        # parsed FreeIPAEntity objects by entity type
        self.entities = dict()

    def load(self, filters=ENTITY_TYPES):
        """
        Parse FreeIPA entity configurations from the given paths.
        """
        paths = self._retrieve_paths(filters)
        for conftype in sorted(paths):
            self.entities[conftype] = list()
            self.lg.debug('Loading %s configs', conftype)
            subpaths = paths[conftype]
            errcount = 0
            for path in subpaths:
                fname = self._short_path(path)
                self.lg.debug('Loading config from %s', fname)
                try:
                    with open(path, 'r') as confsource:
                        data = yaml.safe_load(confsource)
                    self._check_data(data, conftype)
                    parsed = self._parse(data, conftype)
                    if len(parsed) > 1:
                        self.lg.warning(
                            'More than one entity parsed from %s (%d).',
                            fname, len(parsed))
                    self.entities[conftype].extend(parsed)
                except (IOError, ConfigError, yaml.YAMLError) as e:
                    self.lg.error('%s: %s', fname, e)
                    self.errs.append(fname)
                    errcount += 1
            self.lg.info(
                'Parsed %d %s%s', len(self.entities[conftype]), conftype,
                ' (%d errors encountered)' % errcount if errcount else '')

    def _retrieve_paths(self, filters=ENTITY_TYPES):
        """
        Retrieve all available configuration YAML files from the repository.
        :param list filters: types of configurations that should be scanned
                             (e.g. users, hostgroups etc.)
        """
        self.lg.debug('Retrieving paths for filters %s', filters)
        filepaths = dict()
        for conftype in filters:
            subpath = os.path.join(self.basepath, conftype)
            subfiles = glob.glob(subpath + '**/*.yaml')
            if not subfiles:
                self.lg.warning('No %s files found', conftype)
            else:
                self.lg.debug('%s paths to process: %s', conftype, subfiles)
                filepaths[conftype] = subfiles
        return filepaths

    def _check_data(self, data, conftype):
        """
        Check whether data (dictionary of parsed entities)
        is non-empty, correctly structured and non-duplicit.
        :param dict data: dictionary of entities to check
        :param str conftype: type of the checked entities (e.g. users)
        """
        if not data:
            raise ConfigError('Empty config file')
        if not isinstance(data, dict):
            raise ConfigError('Must be a dictionary of entities')
        for ent_name in data:
            if ent_name in [entity.name for entity in self.entities[conftype]]:
                raise ConfigError('Duplicit definition of %s' % ent_name)

    def _short_path(self, path):
        """
        Compose a shorter configuration file path for better log readability
        (relative to the repo path, e.g. users/name.yaml).
        """
        return os.path.join(
            os.path.basename(os.path.dirname(path)), os.path.basename(path))

    def _parse(self, data, conftype):
        """
        Validate data & parse it into FreeIPAEntity representations.
        """
        parser = self.parsers.get(conftype)
        if not parser:
            raise ManagerError('No parser configured for %s' % conftype)
        entities = parser.parse(data)
        self.lg.debug('%s parsed: %s', conftype, entities)
        return entities

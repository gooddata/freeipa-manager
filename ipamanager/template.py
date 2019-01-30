#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.
"""
GoodData FreeIPA tooling

Templating system for deploying new subclusters to FreeIPA
Creates entities locally which then need to be reviewed
and committed to config repository manually

Tomas Bouma <tomas.bouma@gooddata.com>
"""

import entities
import os
import voluptuous
import yaml

from core import FreeIPAManagerCore
from errors import ConfigError
from schemas import schema_template


class FreeIPATemplate(FreeIPAManagerCore):
    """
    Class used for preparing the FreeIPA locally for a given subcluster from a
    template given in input
    When created loads and validates the input data
    :param str name: name of the subcluster
    :param dict data: data from which to create the subcluster
    :param str path_repo: path to freeipa config folder
    """
    def __init__(self, name, data, repo_path, dry_run):
        super(FreeIPATemplate, self).__init__()
        self.path_repo = repo_path
        self.dry_run = dry_run
        self.name = name  # name of the subcluster
        self.data = data  # data prepared for the class
        self.created = []  # list of succesfully created files

    def _create_subcluster(self):
        """
        Creates the aggregate subcluster file for both or one of full and view access
        The subcluster is represented as a usergroup therefore the folder is set
        to group
        """
        for perm, cat_mem_of in (('full', 'full'), ('access', 'view')):
            if self.data['separate_foreman_view'] or perm == 'full':
                node_name = 'aggregate-%s-%s' % (self.name, perm)
                desc = (
                    'Access aggregation (SSH + Foreman view)'
                    'for exporters subcluster')
                data = {'description': desc}
                folder = 'groups'
                member_of = self._member_of_main(cat_mem_of)
                data.update(member_of)
                self.lg.debug('%s data updated with %s', node_name, member_of)
                processed_params = self._process_params(node_name, folder)
                data.update(processed_params)
                self.lg.debug('%s data updated with %s', node_name, processed_params)
                path = os.path.join(self.path_repo, folder, node_name)
                self.created.append(entities.FreeIPAUserGroup(node_name, data, path))
                self.lg.debug('%s created successfully', node_name)

    def _member_of_main(self, cat):
        """
        Creates the memberof attributes for the aggregate subcluster entities
        :param str cat: category depending on rights of a given subcluster one of full/view
        :returns: memberof attributes for the main config file of a given subcluster
        :rtype dict
        """
        member_of = []
        for location, ids in self.data['datacenters'].iteritems():
            for id_num in ids:
                for name, perm in (('foreman', cat), ('primitive', 'full-access')):
                    member_of.append('%s-%s-%s-%s-%s' % (
                        name, self.name, location, id_num, perm))
        return {'memberOf': {'group': sorted(member_of)}}

    def _create_groups(self, location, id_num):
        """
        Creates groups for given location and id for a subcluster
        :param str location: location of the datacenter where the group belongs
        :param int id_num: id_num of the datacenter where the group belongs
        """
        for prefix in ('foreman', 'primitive'):
            for perm in ('view', 'full'):
                if perm == 'full' or self.data['separate_foreman_view']:
                    node_name = '%s-%s-%s-%s-%s' % (
                        prefix, self.name, location, id_num, perm)
                    if prefix == 'primitive':
                        node_name = '%s-access' % node_name
                        if perm == 'view':
                            continue
                    desc = '%s-%s-%s-%s' % (
                        self.name, id_num, location, perm)
                    folder = 'groups'
                    data = {'description': desc}
                    processed_params = self._process_params(node_name, folder, prefix)
                    data.update(processed_params)
                    self.lg.debug('%s data updated with %s', node_name, processed_params)
                    path = os.path.join(
                        self.path_repo, folder, node_name)
                    self.created.append(entities.FreeIPAUserGroup(node_name, data, path))
                    self.lg.debug('%s created successfully', node_name)

    def _create_hostgroup(self, location, id_num):
        """
        Creates one single hostgroup for a subcluster
        :param str location: location of the datacenter where the hostgroup belongs
        :param int id_num: id_num of the datacenter where the ghostgroup belongs
        """
        node_name = '%s-%s' % (self.name, id_num)
        desc = '%s %s subcluster nodes' % (location, self.name)
        data = {'description': desc}
        folder = 'hostgroups'
        processed_params = self._process_params(node_name, folder)
        data.update(processed_params)
        self.lg.debug('%s data updated with %s', node_name, processed_params)
        path = os.path.join(
            self.path_repo, folder, node_name)
        self.created.append(entities.FreeIPAHostGroup(node_name, data, path))
        self.lg.debug('%s created successfully', node_name)

    def _create_rule(self, location, id_num):
        """
        Creates one single rule for a subcluster
        :param str location: location of the datacenter where the rule belongs
        :param int id_num: id_num of the datacenter where the rule belongs
        """
        for file_name, access, folder, entity in (
                ('full-access', 'full', 'hbacrules', entities.FreeIPAHBACRule),
                ('sudo', 'Sudo', 'sudorules', entities.FreeIPASudoRule)):
            if self.data['separate_sudo'] or folder == 'hbacrules':
                node_name = '%s-%s-%s-%s' % (
                    self.name, location, id_num, file_name)
                desc = '%s access to %s subcluster in %s' % (
                    access, self.name, location)
                member_host = ['%s-%s' % (self.name, id_num)]
                member_user = ['primitive-%s-%s-%s-full-access' % (
                    self.name, location, id_num)]
                data = {
                    'description': desc,
                    'memberHost': member_host,
                    'memberUser': member_user
                }
                processed_params = self._process_params(node_name, 'rules', folder)
                data.update(processed_params)
                self.lg.debug('%s data updated with %s', node_name, processed_params)
                path = os.path.join(self.path_repo, folder, node_name)
                self.created.append(entity(node_name, data, path))
                self.lg.debug('%s created successfully', node_name)

    def _create_entities(self):
        """
        Calls the functions create_rules/groups/hostgroups
        :return list of succ created files
        """
        for location, ids in self.data['datacenters'].iteritems():
            for id_num in ids:
                self._create_rule(location, id_num)
                self._create_hostgroup(location, id_num)
                self._create_groups(location, id_num)

    def _process_params(self, name, folder, cat=''):
        """
        Processes the params specified in the config file for each of the node created
        for more info see Documentation
        :param str name: name of the file
        :param str folder: folder where it belongs rules/groups/hostgroups...
        :param str cat: category special params for sudo/hbac rules and foreman/primitive groups
        :return processed params
        :rtype dict
        """
        params = self._process_params_spec(name, folder, cat, self.data.get('include_params', {}))
        meta = self._process_params_spec(name, folder, cat, self.data.get('include_metaparams', {}))
        if meta:
            params['metaparams'] = meta
        return params

    def _process_params_spec(self, name, folder, cat, params):
        """
        Processes either params or metaparams
        :param str name: name of the file
        :param str folder: folder where it belongs rules/groups/hostgroups...
        :param str cat: category special params for sudo/hbac rules and foreman/primitive groups
        :param dict params: params which will be processed one of params/metaparams from the template
        """
        processed = {}
        if 'all' in params:
            for key, value in params['all'].iteritems():
                processed[key] = value
        folder_params = params.get(folder, {})
        for key in ('all', cat, name):
            processed.update(folder_params.get(key, {}))
        return processed

    def _dump_entities(self):
        """Dumps entities that were created during the process"""
        for entity in self.created:
            entity.write_to_file()
        self.lg.debug('Entities were dumped succesfully')

    def create(self):
        """Creates all the files for a subcluster"""
        self._create_subcluster()
        self._create_entities()
        if not self.dry_run:
            self._dump_entities()
            self.lg.info('Succesfully created YAML files: %s', sorted(self.created))
            self.lg.info('Please review them manually and then commit them')
        else:
            self.lg.info('Would create YAML files: %s', sorted(self.created))
            self.lg.info('Run without -d option to create')


class ConfigTemplateLoader(FreeIPAManagerCore):
    def __init__(self, config_path):
        super(ConfigTemplateLoader, self).__init__()
        self.config_path = config_path

    def load_config(self):
        """
        Loads the config according to which the subcluster will be created
        :param str path: path to given config file
        :return dict of data which have been loaded
        :rtype dict
        """
        self.lg.debug('Opening template config file %s', self.config_path)
        try:
            with open(self.config_path, 'r') as f:
                data = list(yaml.safe_load_all(f))
        except IOError as e:
            raise ConfigError(
                'Error reading config file %s: %s' % (self.config_path, e))
        except yaml.YAMLError as e:
            raise ConfigError(
                'Error parsing config file %s: %s' % (self.config_path, e))
        self.lg.debug('Succesfully loaded config file %s', self.config_path)
        self._validate(data)
        return data

    def _validate(self, data):
        """
        Validates the parsed data
        :param list data: to be validated
        """
        try:
            schema = voluptuous.Schema(schema_template)
            for template in data:
                schema(template)
            self.lg.debug('Successfully validated config file')
        except voluptuous.Error as e:
            raise ConfigError(
                'Error validating config file %s: %s'
                % (self.config_path, e))

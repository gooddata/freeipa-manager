#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
# Copyright © 2017-2019, GoodData Corporation. All rights reserved.
import logging
import os
import pytest
import yaml

from _utils import _import
from testfixtures import log_capture

tool = _import('ipamanager', 'template')
errors = _import('ipamanager', 'errors')


class TestTemplate(object):
    def setup_method(self, method):
        self.data = {
            'datacenters': {'xx': [42, 666], 'yy': [19], 'zz': [15]},
            'include_params': {
                'all': {'description': 'all description'},
                'rules': {
                    'all': {
                        'description': 'all_rules_desc'},
                    'sudorules': {
                        'runAsGroupCategory': 'all'},
                    'hbacrules': {
                        'memberService': ['me', 'you']}},
                'hostgroups': {
                    'whole_name': {'description': 'whole hostgroup description'}},
                'groups': {
                    'all': {'posix': True}, 'main': {'posix': True},
                    'foreman': {'posix': False},
                    'primitive': {'posix': True},
                    'whole_name': {'posix': True}}},
                'separate_sudo': False,
                'separate_foreman_view': False,
                'include_metaparams': {'all': {'meta': 'param'}}}
        self.name_data = {'dummy': self.data}
        self.template_tool = tool.FreeIPATemplate('dummy', self.data, 'dummy_path', True)
        self.loader = tool.ConfigTemplateLoader('tests/example_template.yaml')

    def test_tool_creation(self):
        assert self.template_tool.dry_run
        assert self.template_tool.path_repo == 'dummy_path'
        assert self.template_tool.name == 'dummy'
        assert self.template_tool.data == self.data
        assert self.template_tool.created == []

    def test_process_params_whole_name_rules(self):
        self.template_tool.data['include_params']['rules']['sudorules']['description'] = 'sudo description'
        self.template_tool.data['include_params']['rules']['dummy'] = {'description': 'whole name description'}
        assert self.template_tool._process_params('dummy', 'rules', 'sudorules') == {
            'runAsGroupCategory': 'all', 'metaparams': {
                'meta': 'param'}, 'description': 'whole name description'}

    def test_process_params_category_sudo_rules(self):
        self.template_tool.data['include_params']['rules']['sudorules']['description'] = 'sudo description'
        assert self.template_tool._process_params('dummy', 'rules', 'sudorules') == {
            'runAsGroupCategory': 'all', 'metaparams': {
                'meta': 'param'}, 'description': 'sudo description'}

    def test_process_params_category_hbac_rules(self):
        self.template_tool.data['include_params']['rules']['hbacrules']['description'] = 'hbac description'
        assert self.template_tool._process_params('dummy', 'rules', 'hbacrules') == {
            'metaparams': {'meta': 'param'}, 'description': 'hbac description', 'memberService': ['me', 'you']}

    def test_process_params_rules_category_all(self):
        assert self.template_tool._process_params('dummy', 'rules', 'hbacrules') == {
            'memberService': ['me', 'you'], 'metaparams': {'meta': 'param'}, 'description': 'all_rules_desc'}

    def test_process_params_hostgroups_name(self):
        assert self.template_tool._process_params('dummy', 'hostgroups') == {
            'description': 'all description', 'metaparams': {'meta': 'param'}}

    def test_process_params_groups_whole_name(self):
        assert self.template_tool._process_params('whole_name', 'groups', 'foreman') == {
            'posix': True, 'description': 'all description', 'metaparams': {'meta': 'param'}}

    def test_create_subcluster_separate_false(self):
        self.template_tool._create_subcluster()
        assert self.template_tool.created[0].name == 'aggregate-dummy-full'
        assert self.template_tool.created[0].data_repo == {'memberOf': {'group': [
            'foreman-dummy-xx-42-full', 'foreman-dummy-xx-666-full', 'foreman-dummy-yy-19-full',
            'foreman-dummy-zz-15-full', 'primitive-dummy-xx-42-full-access', 'primitive-dummy-xx-666-full-access',
            'primitive-dummy-yy-19-full-access', 'primitive-dummy-zz-15-full-access']},
            'description': 'all description', 'posix': True}
        assert self.template_tool.created[0].path == 'dummy_path/groups/aggregate_dummy_full.yaml'

    def test_create_subcluster_separate_true(self):
        self.data['separate_foreman_view'] = True
        test_tool = tool.FreeIPATemplate('dummy', self.data, 'dummy_path', True)
        test_tool._create_subcluster()

        assert test_tool.created[0].name == 'aggregate-dummy-full'
        assert test_tool.created[0].data_repo == {'description': 'all description', 'memberOf': {'group': [
            'foreman-dummy-xx-42-full', 'foreman-dummy-xx-666-full', 'foreman-dummy-yy-19-full',
            'foreman-dummy-zz-15-full', 'primitive-dummy-xx-42-full-access', 'primitive-dummy-xx-666-full-access',
            'primitive-dummy-yy-19-full-access', 'primitive-dummy-zz-15-full-access']}, 'posix': True}
        assert test_tool.created[0].path == 'dummy_path/groups/aggregate_dummy_full.yaml'

        assert test_tool.created[1].name == 'aggregate-dummy-access'
        assert test_tool.created[1].data_repo == {'description': 'all description', 'memberOf': {'group': [
            'foreman-dummy-xx-42-view', 'foreman-dummy-xx-666-view', 'foreman-dummy-yy-19-view',
            'foreman-dummy-zz-15-view', 'primitive-dummy-xx-42-full-access', 'primitive-dummy-xx-666-full-access',
            'primitive-dummy-yy-19-full-access', 'primitive-dummy-zz-15-full-access']}, 'posix': True}
        assert test_tool.created[1].path == 'dummy_path/groups/aggregate_dummy_access.yaml'

    def test_create_groups(self):
        self.template_tool._create_groups('tak', '1')
        assert len(self.template_tool.created) == 2
        assert self.template_tool.created[0].name == 'foreman-dummy-tak-1-full'
        assert self.template_tool.created[1].name == 'primitive-dummy-tak-1-full-access'
        assert self.template_tool.created[0].path == 'dummy_path/groups/foreman_dummy_tak_1_full.yaml'
        assert self.template_tool.created[1].path == 'dummy_path/groups/primitive_dummy_tak_1_full_access.yaml'
        assert self.template_tool.created[0].data_repo == {'description': 'all description', 'posix': False}
        assert self.template_tool.created[1].data_repo == {'description': 'all description', 'posix': True}

    def test_create_separate_group(self):
        self.data['separate_foreman_view'] = True
        test_tool = tool.FreeIPATemplate('dummy', self.data, 'dummy_path', True)
        test_tool._create_groups('tak', '1')
        assert len(test_tool.created) == 3
        assert test_tool.created[0].name == 'foreman-dummy-tak-1-view'
        assert test_tool.created[1].name == 'foreman-dummy-tak-1-full'
        assert test_tool.created[2].name == 'primitive-dummy-tak-1-full-access'
        assert test_tool.created[0].path == 'dummy_path/groups/foreman_dummy_tak_1_view.yaml'
        assert test_tool.created[1].path == 'dummy_path/groups/foreman_dummy_tak_1_full.yaml'
        assert test_tool.created[2].path == 'dummy_path/groups/primitive_dummy_tak_1_full_access.yaml'
        assert test_tool.created[0].data_repo == {'description': 'all description', 'posix': False}
        assert test_tool.created[1].data_repo == {'description': 'all description', 'posix': False}
        assert test_tool.created[2].data_repo == {'description': 'all description', 'posix': True}

    def test_create_hostgroup(self):
        self.template_tool._create_hostgroup('xx', '666')
        assert len(self.template_tool.created) == 1
        assert self.template_tool.created[0].name == 'dummy-666'
        assert self.template_tool.created[0].path == 'dummy_path/hostgroups/dummy_666.yaml'
        assert self.template_tool.created[0].data_repo == {'description': 'all description'}

    def test_create_rule_separate_false(self):
        self.template_tool._create_rule('xx', '666')
        assert len(self.template_tool.created) == 1
        assert self.template_tool.created[0].name == 'dummy-xx-666-full-access'
        assert self.template_tool.created[0].path == 'dummy_path/hbacrules/dummy_xx_666_full_access.yaml'
        assert self.template_tool.created[0].data_repo == {
            'description': 'all_rules_desc', 'memberUser': ['primitive-dummy-xx-666-full-access'],
            'memberHost': ['dummy-666'], 'memberService': ['me', 'you']}

    def test_create_rule_separate_true(self):
        self.data['separate_sudo'] = True
        test_tool = tool.FreeIPATemplate('dummy', self.data, 'dummy_path', True)
        test_tool._create_rule('xx', '666')
        assert len(test_tool.created) == 2
        assert test_tool.created[0].name == 'dummy-xx-666-full-access'
        assert test_tool.created[0].path == 'dummy_path/hbacrules/dummy_xx_666_full_access.yaml'
        assert test_tool.created[0].data_repo == {
            'description': 'all_rules_desc', 'memberUser': ['primitive-dummy-xx-666-full-access'],
            'memberHost': ['dummy-666'], 'memberService': ['me', 'you']}
        assert test_tool.created[1].name == 'dummy-xx-666-sudo'
        assert test_tool.created[1].path == 'dummy_path/sudorules/dummy_xx_666_sudo.yaml'
        assert test_tool.created[1].data_repo == {
            'description': 'all_rules_desc', 'options': ['!authenticate', '!requiretty'],
            'memberUser': ['primitive-dummy-xx-666-full-access'], 'memberHost': ['dummy-666'],
            'cmdCategory': 'all', 'runAsGroupCategory': 'all', 'runAsUserCategory': 'all'}

    @log_capture('FreeIPATemplate', level=logging.INFO)
    def test_create_sudo_false_foreman_false(self, captured_log):
        tool.FreeIPATemplate('dummy', self.data, 'dummy_path', True).create()
        captured_log.check(('FreeIPATemplate', 'INFO', (
            "Would create YAML files: [group aggregate-dummy-full, hostgroup dummy-15,"
            " hostgroup dummy-19, hostgroup dummy-42, hostgroup dummy-666, hbacrule"
            " dummy-xx-42-full-access, hbacrule dummy-xx-666-full-access, hbacrule dummy-yy-19-full-access,"
            " hbacrule dummy-zz-15-full-access, group foreman-dummy-xx-42-full, group foreman-dummy-xx-666-full,"
            " group foreman-dummy-yy-19-full, group foreman-dummy-zz-15-full, group primitive-dummy-xx-42-full-access,"
            " group primitive-dummy-xx-666-full-access, group primitive-dummy-yy-19-full-access, group"
            " primitive-dummy-zz-15-full-access]")), ('FreeIPATemplate', 'INFO', 'Run without -d option to create'))

    @log_capture('FreeIPATemplate', level=logging.INFO)
    def test_create_sudo_true_foreman_false(self, captured_log):
        self.data['separate_sudo'] = True
        tool.FreeIPATemplate('dummy', self.data, 'dummy_path', True).create()
        captured_log.check(('FreeIPATemplate', 'INFO', (
            "Would create YAML files: [group aggregate-dummy-full, hostgroup dummy-15, hostgroup dummy-19,"
            " hostgroup dummy-42, hostgroup dummy-666, hbacrule dummy-xx-42-full-access, sudorule dummy-xx-42-sudo,"
            " hbacrule dummy-xx-666-full-access, sudorule dummy-xx-666-sudo, hbacrule dummy-yy-19-full-access, "
            "sudorule dummy-yy-19-sudo, hbacrule dummy-zz-15-full-access, sudorule dummy-zz-15-sudo, group "
            "foreman-dummy-xx-42-full, group foreman-dummy-xx-666-full, group foreman-dummy-yy-19-full, "
            "group foreman-dummy-zz-15-full, group primitive-dummy-xx-42-full-access, group "
            "primitive-dummy-xx-666-full-access, group primitive-dummy-yy-19-full-access,"
            " group primitive-dummy-zz-15-full-access]")),
            ('FreeIPATemplate', 'INFO', 'Run without -d option to create'))

    @log_capture('FreeIPATemplate', level=logging.INFO)
    def test_create_sudo_false_foreman_true(self, captured_log):
        self.data['separate_foreman_view'] = True
        tool.FreeIPATemplate('dummy', self.data, 'dummy_path', True).create()
        captured_log.check(('FreeIPATemplate', 'INFO', (
            "Would create YAML files: [group aggregate-dummy-access, group aggregate-dummy-full, hostgroup dummy-15,"
            " hostgroup dummy-19, hostgroup dummy-42, hostgroup dummy-666, hbacrule dummy-xx-42-full-access, hbacrule"
            " dummy-xx-666-full-access, hbacrule dummy-yy-19-full-access, hbacrule dummy-zz-15-full-access, group "
            "foreman-dummy-xx-42-full, group foreman-dummy-xx-42-view, group foreman-dummy-xx-666-full, group "
            "foreman-dummy-xx-666-view, group foreman-dummy-yy-19-full, group foreman-dummy-yy-19-view, group "
            "foreman-dummy-zz-15-full, group foreman-dummy-zz-15-view, group primitive-dummy-xx-42-full-access,"
            " group primitive-dummy-xx-666-full-access, group primitive-dummy-yy-19-full-access, group "
            "primitive-dummy-zz-15-full-access]")),
            ('FreeIPATemplate', 'INFO', 'Run without -d option to create'))

    @log_capture('FreeIPATemplate', level=logging.INFO)
    def test_create_sudo_true_foreman_true(self, captured_log):
        self.data['separate_foreman_view'] = True
        self.data['separate_sudo'] = True
        tool.FreeIPATemplate('dummy', self.data, 'dummy_path', True).create()
        captured_log.check(('FreeIPATemplate', 'INFO', (
            "Would create YAML files: [group aggregate-dummy-access, group aggregate-dummy-full, hostgroup "
            "dummy-15, hostgroup dummy-19, hostgroup dummy-42, hostgroup dummy-666, hbacrule dummy-xx-42-full-access,"
            " sudorule dummy-xx-42-sudo, hbacrule dummy-xx-666-full-access, sudorule dummy-xx-666-sudo, hbacrule "
            "dummy-yy-19-full-access, sudorule dummy-yy-19-sudo, hbacrule dummy-zz-15-full-access, sudorule "
            "dummy-zz-15-sudo, group foreman-dummy-xx-42-full, group foreman-dummy-xx-42-view, group "
            "foreman-dummy-xx-666-full, group foreman-dummy-xx-666-view, group foreman-dummy-yy-19-full,"
            " group foreman-dummy-yy-19-view, group foreman-dummy-zz-15-full, group foreman-dummy-zz-15-view,"
            " group primitive-dummy-xx-42-full-access, group primitive-dummy-xx-666-full-access, group "
            "primitive-dummy-yy-19-full-access, group primitive-dummy-zz-15-full-access]")),
            ('FreeIPATemplate', 'INFO', 'Run without -d option to create'))

    def test_dump_files(self, tmpdir):
        self.template_tool.path_repo = tmpdir.strpath
        self.template_tool._create_hostgroup('xx', '666')
        tmpdir.mkdir('hostgroups')
        self.template_tool._dump_entities()
        assert os.listdir(os.path.join(tmpdir.strpath, 'hostgroups')) == ['dummy_666.yaml']
        with open(os.path.join(tmpdir.strpath, 'hostgroups/dummy_666.yaml'), 'r') as f:
            assert yaml.load(f) == {'dummy-666': {'description': 'all description', 'metaparams': {'meta': 'param'}}}

    def test_load_data(self):
        loaded = self.loader.load_config()
        assert loaded[0] == self.name_data
        assert len(loaded) == 1

    @log_capture('', level=logging.DEBUG)
    def test_validate_correctt(self, captured_log):
        self.loader._validate([self.name_data])
        captured_log.check(('ConfigTemplateLoader', 'DEBUG', 'Successfully validated config file'),)

    def test_validate_wrong(self):
        self.name_data['dummy'].pop('datacenters')
        with pytest.raises(errors.ConfigError) as exc:
            self.loader._validate([self.name_data])
        assert exc.value[0] == (
            "Error validating config file tests/example_template.yaml: required key"
            " not provided @ data['dummy']['datacenters']")

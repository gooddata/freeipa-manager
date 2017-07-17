"""
GoodData FreeIPA tooling
IPA updating tool

Tool for updating a FreeIPA server via API
from local entity configuration.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

from ipalib import api

import entities
from command import Command
from core import FreeIPAManagerCore
from entities import FreeIPAEntity
from errors import CommandError, ManagerError
from utils import ENTITY_CLASSES


class IpaConnector(FreeIPAManagerCore):
    """
    Responsible for updating FreeIPA server with changed configuration.
    """
    def __init__(self, parsed, threshold, force=False,
                 enable_deletion=False, debug=False):
        """
        Initialize an IPA connector object.
        :param dict parsed: dictionary of entities from `IntegrityChecker`
        :param int threshold: max percentage of entities to edit (1-100)
        :param bool force: execute changes (dry run if False)
        :param bool enable_deletion: enable deleting entities
        :param bool debug: verbose API library output if True
        """
        super(IpaConnector, self).__init__()
        self.local = parsed
        self.threshold = threshold
        self.force = force
        self.enable_deletion = enable_deletion
        self._init_api_connection(debug)

    def _init_api_connection(self, debug):
        api.bootstrap(context='cli', verbose=debug)
        api.finalize()
        api.Backend.rpcclient.connect()
        self.lg.debug('API connection initialized')

    def load_remote(self):
        """
        Load entities defined on the FreeIPA via API.
        Entity data is saved in `self.remote` dictionary with keys
        being a tuple (entity type, name) (e.g., ('hostgroup', 'group-one')).
        :raises ManagerError: if there is an error communicating with the API
        :returns: None (entities saved in the `self.remote` dict)
        """
        self.lg.debug('Loading entities from FreeIPA API')
        self.remote = dict()
        for entity_class in ENTITY_CLASSES:
            self.remote[entity_class.entity_name] = dict()
            command = '%s_find' % entity_class.entity_name
            self.lg.debug('Running API command %s', command)
            try:
                parsed = api.Command[command](all=True)
            except KeyError:
                raise ManagerError('Undefined API command %s' % command)
            except Exception as e:
                raise ManagerError('Error loading %s entities from API: %s'
                                   % (entity_class.entity_name, e))
            for entity in parsed['result']:
                name = entity[entity_class.entity_id_type][0]
                self.remote[entity_class.entity_name][name] = entity
            self.lg.debug('Found %d %s entities: %s',
                          len(parsed['result']), entity_class.entity_name,
                          sorted(self.remote[entity_class.entity_name].keys()))
        self.remote_count = sum(len(i) for i in self.remote.itervalues())
        self.lg.info('Parsed %d entities from FreeIPA API', self.remote_count)

    def _prepare_commands(self):
        """
        Prepare the queue of commands to execute as part of FreeIPA update.
        The commands include addition/modification/deletion of entities,
        adding/removing group/rule members and sudorule options. Deletion
        commands are only enqueued when `enable_deletion` attribute is True.
        """
        self.lg.debug('Preparing IPA update commands')
        self.commands = []
        for entity_type in self.local:
            self.lg.debug('Processing %s entities', entity_type)
            for entity in self.local[entity_type].itervalues():
                self.lg.debug('Processing entity %s', entity)
                self._parse_entity_diff(entity)
        if self.enable_deletion:
            self._prepare_deletion_commands()
        self.lg.info('%d commands to execute', len(self.commands))

    def _parse_entity_diff(self, entity):
        """
        Prepare update commands for a single entity. This includes creating
        the entity if it doesn't exist or modifying its attributes if it exists
        already. Some attributes require special handling (e.g., group/rule
        membership, which needs to call a command on the group/rule entity, or
        sudorule option add/delete) that is special-cased by auxiliary methods.
        :param FreeIPAEntity entity: local entity instance to process
        """
        remote_entity = self.remote[entity.entity_name].get(entity.name)
        if not isinstance(entity, entities.FreeIPARule):
            self._process_membership(entity)
        commands = entity.create_commands(remote_entity)
        if commands:
            self.commands.extend(commands)

    def _process_membership(self, entity):
        """
        Prepare membership update commands for an entity. This has 2 phases:
        1. ensure addition to groups listed in entity's memberOf attribute
        2. iterate over all remote groups, ensure deletion from groups that
           have been deleted from the memberOf attribute
        :param FreeIPAEntity entity: entity to process
        """
        self.lg.debug('Processing membership for %s', entity)
        member_of = entity.data.get('memberOf', dict())
        key = 'member_%s' % entity.entity_name
        for target_type in member_of:
            for target_name in member_of[target_type]:
                local_group = self.local[target_type][target_name]
                remote_group = self.remote[target_type].get(target_name)
                if remote_group and entity.name in remote_group.get(key, []):
                    self.lg.debug(
                        '%s already member of %s', entity, local_group)
                    continue
                command = '%s_add_member' % local_group.entity_name
                self.commands.append(
                    Command(command, {entity.entity_name: (entity.name,)},
                            local_group.name, local_group.entity_id_type))
        # FIXME target types should be based on membership rules YAML
        if isinstance(entity, entities.FreeIPAUser):
            target_type = 'group'
        else:
            target_type = entity.entity_name
        for group_name, group in self.remote[target_type].iteritems():
            if (target_type, group_name) == ('group', 'ipausers'):
                continue
            members = group.get('member_%s' % entity.entity_name, [])
            if entity.name in members:
                if group_name not in member_of.get(target_type, []):
                    command = '%s_remove_member' % target_type
                    diff = {entity.entity_name: (entity.name,)}
                    self.commands.append(
                        Command(command, diff, group_name, 'cn'))

    def _prepare_deletion_commands(self):
        """
        Prepare commands to handle deletion of entities that are not in config.
        This is only called if the `enable_deletion` flag is set to True.
        """
        for entity_type in self.remote:
            entity_class = FreeIPAEntity.get_entity_class(entity_type)
            self.lg.debug('Preparing deletion of %s entities', entity_type)
            for name, entity in self.remote[entity_type].iteritems():
                if name not in self.local.get(entity_type, dict()):
                    self.lg.debug('Marking %s for deletion', name)
                    command = '%s_del' % entity_type
                    self.commands.append(
                        Command(
                            command, {}, name, entity_class.entity_id_type))

    def execute_update(self):
        """
        Execute update by running commands from the execution queue
        prepared by the `prepare_update` method.
        Commands will only be executed if their total number does not
        exceed the `threshold` attribute.
        :raises ManagerError: in case of exceeded threshold/API error
        """
        self._prepare_commands()
        if not self.commands:
            self.lg.info('FreeIPA consistent with local config, nothing to do')
            return
        if not self.force:  # dry run
            self.lg.info('Would execute commands:')
            for command in sorted(self.commands):
                self.lg.info('- %s', command)
        self._check_threshold()
        if self.force:
            # command sorting really important here for correct update!
            for command in sorted(self.commands):
                try:
                    command.execute(api)
                except CommandError as e:
                    self.errs.append((command.description, str(e)))
            if self.errs:
                raise ManagerError(
                    'There were %d errors executing update' % len(self.errs))

    def _check_threshold(self):
        if not self.remote_count:  # avoid divison by zero on empty IPA
            ratio = 100
        else:
            ratio = 100 * float(len(self.commands))/self.remote_count
        self.lg.debug('%d commands, %d remote entities (%.2f %%)',
                      len(self.commands), self.remote_count, ratio)
        if ratio > self.threshold:
            raise ManagerError(
                'Threshold exceeded (%.2f %% > %.f %%), aborting'
                % (ratio, self.threshold))
        self.lg.debug('Threshold check passed')

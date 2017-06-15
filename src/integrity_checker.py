"""
GoodData FreeIPA tooling
Integrity checking tool

Tools for checking integrity of entity configurations.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import entities
from core import FreeIPAManagerCore
from errors import IntegrityError


class IntegrityChecker(FreeIPAManagerCore):
    def __init__(self, parsed):
        """
        Create an integrity checker instance.
        :param dict parsed: entities parsed by `ConfigLoader` to check
        """
        super(IntegrityChecker, self).__init__()
        self._build_dict(parsed)

    def check(self):
        """
        Run an integrity check over the whole parsed configuration dictionary.
        It is checked that entity having members exist and that users
        are not members of meta groups.
        :raises IntegrityError: if there is a problem with config integrity
        :returns: None (everything correct if no error is raised)
        """
        if not self.entity_dict:
            self.lg.warning('No entities to check for integrity')
            return
        self.lg.info('Running parsed entities integrity check')
        self.errs = dict()
        for entity in sorted(self.entity_dict.values(),
                             key=lambda e: (e.entity_name, e.name)):
            self._check_single(entity)
        if self.errs:
            raise IntegrityError(
                'There were %d integrity errors in %d entities' %
                (sum(len(i) for i in self.errs.itervalues()), len(self.errs)))
        self.lg.info('Integrity check passed')

    def _check_single(self, entity):
        """
        Check integrity of a given entity. Membership validity
        is verified as part of this check (using the `_check_memberof` method).
        :param FreeIPAEntity entity: entity to check
        """
        self.lg.debug('Checking entity %s', entity.dn)
        errs = self._check_memberof(entity)
        if errs:
            self.lg.error('%s: %s', entity.name, '; '.join(errs))
            self.errs[entity.dn] = errs
        elif isinstance(entity, entities.FreeIPAGroup):
            self._check_cycles(entity)

    def _check_memberof(self, entity):
        """
        Check if membership relations of an entity are correct
        (i.e. entity is only a member of existing entities,
        user is not a member of meta groups).
        :param FreeIPAEntity entity: entity to check
        :returns: list of error messages (empty list if everything OK)
        :rtype: list(str)
        """
        errs = []
        member_of = entity.data.get('memberOf', [])
        for item in member_of:
            target = self.entity_dict.get(item)
            if not target:
                errs.append('memberOf non-existent entity %s' % item)
                continue
            if target == entity:
                errs.append('memberOf itself')
                continue
            if not self._check_memberof_meta(entity, target):
                errs.append('memberOf meta group %s' % target)
        return errs

    def _check_memberof_meta(self, entity, target):
        """
        Check if metagroup membership is not violated
        (i.e. whether a user is not a member of a meta usergroup).
        :param FreeIPAEntity entity: entity to check
        :param FreeIPAEntity target: membership target entity
        :returns: True if membership is correct, False in case of violation
        :rtype: bool
        """
        if isinstance(entity, entities.FreeIPAUser):
            if isinstance(target, entities.FreeIPAGroup) and target.is_meta:
                return False
        return True

    def _check_cycles(self, entity):
        """
        Check if there is a membership cycle in the config starting at entity.
        Only called on groups as no other entities can have cyclic membership.
        :param FreeIPAGroup entity: entity (group) to begin checking at
        :raises IntegrityError: if there is a circular relationship
        :returns: None (everything correct if error is not raised)
        """
        self.lg.debug('Running cycles check for %s', entity.dn)
        stack = [(entity, [])]
        visited = set()
        while stack:
            current, path = stack.pop()
            visited.add(current)
            path.append(current)
            for target_dn in current.data.get('memberOf', []):
                target = self.entity_dict[target_dn]
                if target == entity:
                    raise IntegrityError(
                        'Cyclic membership of %s %s' %
                        (entity.entity_name, path))
                if target not in visited:
                    stack.append((target, path))

    def _build_dict(self, parsed):
        """
        Build a dictionary of all entities so that entities
        can be easily looked up by their DN.
        :param dict parsed: entities parsed by `ConfigLoader` to process
        :returns: None (the `entity_dict` attribute is set)
        """
        self.entity_dict = dict()
        for entity_list in parsed.itervalues():
            for e in entity_list:
                self.entity_dict[e.dn] = e

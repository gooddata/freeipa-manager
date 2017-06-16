"""
GoodData FreeIPA tooling
Integrity checking tool

Tools for checking integrity of entity configurations.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import re
import yaml

import entities
from core import FreeIPAManagerCore
from errors import IntegrityError, ManagerError


class IntegrityChecker(FreeIPAManagerCore):
    def __init__(self, rules_file, parsed):
        """
        Create an integrity checker instance.
        :param str rules_file: path to integrity check rules file
        :param dict parsed: entities parsed by `ConfigLoader` to check
        """
        super(IntegrityChecker, self).__init__()
        self._load_rules(rules_file)
        self._build_dict(parsed)

    def check(self):
        """
        Run an integrity check over the whole parsed configuration dictionary.
        :raises IntegrityError: if there is a problem with config integrity
        :returns: None (everything correct if no error is raised)
        """
        if not self.entity_dict:
            self.lg.warning('No entities to check for integrity')
            return
        self.errs = dict()
        for entity in self.entity_dict.itervalues():
            self._check_single(entity)
        if self.errs:
            raise IntegrityError(
                'There were %d integrity errors in %d entities' %
                (sum(len(i) for i in self.errs.itervalues()), len(self.errs)))
        self.lg.info('Integrity check passed')

    def _check_single(self, entity):
        """
        Check integrity of a single entity. It is verified that it is only
        a member of existing entities (and not of itself), that membership
        adheres to rules defined in the rules file, and that there is no cyclic
        membership (if the entity is a group).
        :param FreeIPAEntity entity: entity to check
        :returns: None (any errors are written to the `self.errs` dictionary)
        """
        if isinstance(entity, entities.FreeIPARule):
            errs = self._check_single_rule_entity(entity)
        else:
            errs = self._check_single_member_entity(entity)
        if errs:
            self.lg.error(
                '%s (%s): %s', entity.name,
                entity.entity_name, '; '.join(errs))
            self.errs[entity.dn] = errs

    def _check_single_rule_entity(self, entity):
        """
        Run checks specific for rule-type entities (HBAC & sudo rules).
        This special case is necessary as membership representation
        is different for rules (they have memberHost and memberUser attributes
        to represent their members while other entities have memberOf attribute
        that reflects their own membership in other entities).
        :param FreeIPARule entity: rule entity to check
        """
        errs = []
        for key, member_type in [
                ('memberHost', entities.FreeIPAHostGroup),
                ('memberUser', entities.FreeIPAUserGroup)]:
            member_name = entity.data.get(key)
            if not member_name:
                errs.append('no %s' % key)
                continue
            member_name = member_name[0]  # LDAP stores everything as list
            member = self.entity_dict.get(member_name)
            if not member:
                errs.append('non-existent %s %s' % (key, member_name))
                continue
            try:
                self._check_member_rules(member, key, entity)
            except IntegrityError as e:
                errs.append(str(e))
        return errs

    def _check_single_member_entity(self, entity):
        """
        Run checks specific for entities that can be members
        of other entities (i.e. all entities except rules).
        :param FreeIPAEntity entity: entity to check
        """
        errs = []
        for item in entity.data.get('memberOf', []):
            target = self.entity_dict.get(item)
            if not target:
                errs.append('memberOf non-existent entity %s' % item)
                continue
            if target == entity:
                errs.append('memberOf itself')
                continue
            try:
                self._check_member_rules(entity, entity.entity_name, target)
            except IntegrityError as e:
                errs.append(str(e))
                continue
        # check for cyclic membership
        if not errs and isinstance(entity, entities.FreeIPAGroup):
            cyclic_path = self._check_cycles(entity)
            if cyclic_path:
                errs.append('Cyclic membership of %s: %s'
                            % (entity.entity_name, cyclic_path))
        return errs

    def _check_member_rules(self, member, member_name, target):
        """
        Check that the membership between given entities adheres
        to all rules specified in the integrity check rules file.
        :param FreeIPAEntity member: member entity
        :param str member_name: key used to specify member type in rules file
            (for HBAC/sudo rules, this is memberHost/memberUser;
             for other entities, it is normal entity type (hostgroups etc.))
        :param FreeIPAEntity target: membership target entity
        """
        try:
            rules = self.rules[target.entity_name][member_name]
        except KeyError:
            raise IntegrityError(
                'cannot be a member of %s (%s)' % (target.entity_name, target))
        if not rules:
            return
        for rule in rules:
            self._check_member_rule(member, target, rule)

    def _check_member_rule(self, member, target, rule):
        """
        Check whether relationship between `member` and `target` obeys `rule`.
        :param FreeIPAEntity member: checked member entity
        :param FreeIPAEntity target: membership target entity
        :param str rule: rule to check - (member_)(non)meta
        :raises IntegrityError: if a rule is violated
        :returns: None (everything OK if no error is raised)
        """
        match = re.match(r'(member_of_|)(non|)meta', rule)
        if not match:
            raise ManagerError('Undefined rule: %s' % rule)
        member_of, negation = match.groups()
        if member_of:
            checkable = target
            err_msg = '%s must%s be a meta group to have %s as a member' % (
                target, ' not' if negation else '', member)
        else:
            checkable = member
            err_msg = '%s must%s be a meta group to be a member of %s' % (
                member, ' not' if negation else '', target)
        if checkable.is_meta:
            if negation:
                raise IntegrityError(err_msg)
        else:
            if not negation:
                raise IntegrityError(err_msg)

    def _check_cycles(self, entity):
        """
        Check if there is a membership cycle in the config starting at entity.
        Only called on groups as no other entities can have cyclic membership.
        :param FreeIPAGroup entity: entity (group) to begin checking at
        :returns: cyclic membership entity list if found, else None
        """
        self.lg.debug('Running cycles check for %s', entity.dn)
        stack = [(entity, [])]
        visited = set()
        while stack:
            current, path = stack.pop()
            visited.add(current)
            path.append(current)
            for target_dn in current.data.get('memberOf', []):
                target = self.entity_dict.get(target_dn)
                if not target:  # non-existent entity
                    continue
                if target == entity:  # cycle found
                    return path
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

    def _load_rules(self, path):
        """
        Load the rules file for the integrity check
        and generate respective membership checking functions.
        :param str path: path to the rules file
        """
        self.lg.info('Using integrity check rules from %s', path)
        try:
            with open(path) as src:
                    self.rules = yaml.safe_load(src)
        except IOError as e:
            raise ManagerError('Cannot open rules file: %s' % e)
        self.lg.debug('Settings parsed: %s', self.rules)

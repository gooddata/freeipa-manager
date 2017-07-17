"""
GoodData FreeIPA tooling
IPA commands

IPA command objects to execute during FreeIPA update.

Kristian Lesko <kristian.lesko@gooddata.com>
"""

import re

from core import FreeIPAManagerCore
from errors import CommandError


class Command(FreeIPAManagerCore):
    def __init__(self, command, payload, entity_name, entity_id_type):
        """
        Create a FreeIPA API command instance.
        :param str command: name of the command (e.g., user_add)
        :param dict payload: data (modlist) of the change
        :param str entity_name: name of the modified entity
        :param str entity_id_type: type of entity ID attribute (cn/uid)
        :param FreeIPAEntity entity: entity modified by the command
        """
        super(Command, self).__init__()
        self.command = command
        self.entity_name = entity_name
        self.entity_id_type = entity_id_type
        self.payload = payload
        self.payload[self.entity_id_type] = self.entity_name
        self._encode_payload()
        self._create_description()
        self._calculate_rank()

    def _encode_payload(self):
        encoded = dict()
        for key, value in self.payload.iteritems():
            if isinstance(value, unicode) or isinstance(value, str):
                new_value = unicode(value)
            elif len(value) == 1:
                new_value = unicode(value[0])
            else:
                new_value = tuple(unicode(i) for i in value)
            encoded[key.lower()] = new_value
        self.payload = encoded

    def _create_description(self):
        desc_data = [
            '%s=%s' % (k, v[0] if len(v) == 1 else v) for k, v
            in sorted(self.payload.items()) if k != self.entity_id_type]
        self.description = '%s %s (%s)' % (
            self.command, self.entity_name, '; '.join(desc_data))

    def execute(self, api):
        self.lg.info('Executing %s', self.description)
        try:
            result = api.Command[self.command](**self.payload)
            self._handle_output(result)
        except KeyError:
            raise CommandError('Non-existent command %s' % self.command)
        except Exception as e:
            raise CommandError('Error executing %s: %s' % (self.command, e))

    def _handle_output(self, output):
        """
        Parse the result of a command execution from the API response.
        The complicated parsing of the 'failed' key is necessary because
        the key is present in the API response with a non-empty value
        even if no failure has occured.
        """
        if output.get('summary'):
            self.lg.info(output['summary'])
        else:
            errs = []
            if 'failed' in output:
                for key in output['failed'].itervalues():
                    for err in key.itervalues():
                        if err:
                            for item, msg in err:
                                errs.append('- %s: %s' % (item, msg))
            if errs:
                self.lg.error('%s failed:', self.description)
                for i in errs:
                    self.lg.error(i)
                raise CommandError(errs)
            else:
                self.lg.info('%s successful', self.description)

    def __repr__(self):
        return self.description

    def __lt__(self, other):
        if self.rank == other.rank:
            return self.description < other.description
        return self.rank < other.rank

    def _calculate_rank(self):
        patterns = ('.+_add$', '.+_add_.+', '.+_mod$',
                    '.+_remove_.+', '.+_del$')
        rank = 0
        while rank < len(patterns):
            if re.match(patterns[rank], self.command):
                break
            rank += 1
        self.rank = rank

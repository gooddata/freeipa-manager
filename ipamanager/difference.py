import os

from core import FreeIPAManagerCore
from errors import IntegrityError


class FreeIPADifference(FreeIPAManagerCore):
    """
    Class used for showing the set like difference between
    the min and sub path given file names in command line args
    Use run to print the additional entities
    """
    def __init__(self, min_path, sub_path):
        super(FreeIPADifference, self).__init__()
        self.min_path = min_path
        self.sub_path = sub_path

    def _load_dir(self, path):
        result = set()
        for filename in os.listdir(path):
            if os.path.isfile(os.path.join(path, filename)):
                result.add(filename)
        return result

    def run(self):
        min_set = self._load_dir(self.min_path)
        sub_set = self._load_dir(self.sub_path)
        diff = min_set.difference(sub_set)
        if diff:
            raise IntegrityError('The ADDITIONAL entities are : %s' % ' '.join(sorted(diff)))
        else:
            self.lg.info('There are no ADDITIONAL entites')

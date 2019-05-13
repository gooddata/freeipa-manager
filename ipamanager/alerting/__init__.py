import abc
import logging

from ipamanager.core import FreeIPAManagerCore


class AlertingPlugin(FreeIPAManagerCore, logging.Handler):
    """
    Abstract class that should be used as basis for alerting plugins.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, loglevel):
        FreeIPAManagerCore.__init__(self)
        logging.Handler.__init__(self)
        self.messages = []
        self.setLevel(loglevel)
        self.setFormatter(logging.Formatter(fmt='%(levelname)s: %(message)s'))
        self.messages = []
        self.max_level = logging.NOTSET
        self.lg.debug('Alerting plugin %s initialized', self.name)

    def emit(self, record):
        self.messages.append(self.format(record))
        self.max_level = max(self.max_level, record.levelno)

    @abc.abstractmethod
    def dispatch(self):
        """
        Main runtime method of the plugin.
        It should handle actual status dispatch to a monitoring application.
        """

    @property
    def name(self):
        """
        Name of the plugin; used, for instance, for logging purposes.
        """
        return self.__class__.__name__

    def __str__(self):
        return self.name

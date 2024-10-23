import os
from os import environ
from pathlib import Path
from dataclasses import dataclass

class ClassPropertyDescriptor(object):

    def __init__(self, fget, fset=None):
        self.fget = fget
        self.fset = fset

    def __get__(self, obj, klass=None):
        if klass is None:
            klass = type(obj)
        return self.fget.__get__(obj, klass)()

    def __set__(self, obj, value):
        if not self.fset:
            raise AttributeError("can't set attribute")
        type_ = type(obj)
        return self.fset.__get__(obj, type_)(value)

    def setter(self, func):
        if not isinstance(func, (classmethod, staticmethod)):
            func = classmethod(func)
        self.fset = func
        return self

def classproperty(func):
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)
    return ClassPropertyDescriptor(func)

@dataclass(frozen=True)
class Configuration:
    logging_configuration_file : str = environ.get("LOGGING_CONFIGURATION_FILE", Path(__file__).parent / 'default-conf' / 'logging.yaml')
    plant_uml_server_address : str = environ.get('PLANT_UML_SERVER_ADDRESS', None)


    @classproperty
    def instance(cls) -> 'Configuration':
        return Configuration()




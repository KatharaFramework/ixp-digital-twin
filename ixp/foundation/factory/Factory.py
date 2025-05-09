import importlib
from typing import Any

from ..exceptions import ClassNotFoundError


def class_for_name(package_name: str, module_name: str) -> Any:
    m = importlib.import_module(package_name + "." + module_name)
    camel_case_class_name = "".join(map(lambda x: x.capitalize(), module_name.split('_'))) \
        if '_' in module_name else module_name
    return getattr(m, camel_case_class_name)


class Factory(object):
    __slots__ = ['package_template', 'module_template']

    def get_package_name(self, args: tuple) -> str:
        return self.package_template

    def get_class_name(self, args: tuple) -> str:
        return self.module_template % args

    def get_class(self, package_args: tuple = (), class_args: tuple = ()) -> Any:
        package_name = self.get_package_name(package_args)
        class_name = self.get_class_name(class_args)

        try:
            return class_for_name(package_name, class_name)
        except ImportError as e:
            if e.name == "%s.%s" % (package_name, class_name):
                raise ClassNotFoundError
            else:
                raise ImportError from e

    def create_instance(self, package_args: tuple = (), class_args: tuple = ()) -> Any:
        return self.get_class(package_args, class_args)()


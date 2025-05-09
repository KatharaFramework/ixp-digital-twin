from ....foundation.factory.Factory import Factory
from .table_dump import TableDump


class TableDumpFactory(Factory):
    def __init__(self, submodule_package: str = None) -> None:
        self.package_template: str = (f"{submodule_package}." if submodule_package else "") + "ixp.dumps.table_dump"
        self.module_template: str = "%s_table_dump"

    def get_class_from_name(self, dump_type: str) -> TableDump.__class__:
        return self.get_class((dump_type.lower(),), (dump_type.lower(),))

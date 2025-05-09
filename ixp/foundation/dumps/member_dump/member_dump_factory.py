from ....foundation.factory.Factory import Factory
from .member_dump import MemberDump


class MemberDumpFactory(Factory):
    def __init__(self, submodule_package: str = None) -> None:
        self.package_template: str = (f"{submodule_package}." if submodule_package else "") + "ixp.dumps.member_dump"
        self.module_template: str = "%s_dump"

    def get_class_from_name(self, dump_type: str) -> MemberDump.__class__:
        return self.get_class((dump_type.lower(),), (dump_type.lower(),))

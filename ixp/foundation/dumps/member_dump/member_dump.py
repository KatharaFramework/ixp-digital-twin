from abc import ABC

from ....model.bgp_neighbour import BGPNeighbour


class MemberDump(ABC):
    __slots__ = ['_peering_mac_addr', '_as_to_generated_mac']

    def __init__(self) -> None:
        self._peering_mac_addr: int = 1
        self._as_to_generated_mac: dict[int, str] = {}

    @staticmethod
    def load_from_file(self, path: str) -> dict[str, BGPNeighbour]:
        raise NotImplementedError("You must implement `load_from_file` method.")

    def _generate_mac_address(self) -> str:
        mac_hex = f'{self._peering_mac_addr:012X}'
        mac_str = ':'.join(mac_hex[i:i + 2] for i in range(0, 12, 2))

        self._peering_mac_addr += 1

        return mac_str

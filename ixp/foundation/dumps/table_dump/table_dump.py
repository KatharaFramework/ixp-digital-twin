from abc import ABC, abstractmethod

from ....model.bgp_neighbour import BGPNeighbour


class TableDump(ABC):
    __slots__ = ["entries"]

    def __init__(self, entries: dict[str, BGPNeighbour]) -> None:
        self.entries: dict[str, BGPNeighbour] = entries

    @abstractmethod
    def load_from_file(self, path: str) -> None:
        raise NotImplementedError("You must implement `load_from_file` method.")

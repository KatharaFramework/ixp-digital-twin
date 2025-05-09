from abc import ABC, abstractmethod


class VendorFormatParserMixin(ABC):
    @abstractmethod
    def parse_bgp_neighbor_state(self, result: str) -> dict:
        raise NotImplementedError("You must implement `parse_bgp_neighbor_state` method.")

    @abstractmethod
    def parse_bgp_neighbor_rib(self, result: str) -> dict:
        raise NotImplementedError("You must implement `parse_bgp_neighbor_rib` method.")

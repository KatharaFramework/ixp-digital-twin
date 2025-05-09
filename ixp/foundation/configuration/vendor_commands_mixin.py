import ipaddress
from abc import ABC, abstractmethod

from Kathara.model.Machine import Machine


class VendorCommandsMixin(ABC):
    @abstractmethod
    def command_config_reload(self, device: Machine) -> str:
        raise NotImplementedError("You must implement `command_config_reload` method.")

    @abstractmethod
    def command_neighbor_info(self, device: Machine, session_ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
        raise NotImplementedError("You must implement `command_neighbor_info` method.")

    @abstractmethod
    def command_neighbor_rib(self, device: Machine, session_ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
        raise NotImplementedError("You must implement `command_neighbor_rib` method.")

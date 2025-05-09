from abc import ABC, abstractmethod

from Kathara.model.Lab import Lab

from ...model.bgp_neighbour import BGPNeighbour
from ...network_scenario.rs_manager import RouteServerManager


class Action(ABC):
    @abstractmethod
    def verify(
            self, net_scenario: Lab, members: dict[str, BGPNeighbour], rs_manager: RouteServerManager, **kwargs
    ) -> 'ActionResult':
        raise NotImplementedError("You must implement `verify` method.")

    def clean(
            self, net_scenario: Lab, members: dict[str, BGPNeighbour], rs_manager: RouteServerManager, **kwargs
    ) -> None:
        pass

    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError("You must implement `name` method.")

    @abstractmethod
    def display_name(self) -> str:
        raise NotImplementedError("You must implement `display_name` method.")

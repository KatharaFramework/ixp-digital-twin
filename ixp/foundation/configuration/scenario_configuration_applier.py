from abc import ABC, abstractmethod
from typing import Callable

from Kathara.model.Lab import Lab
from Kathara.model.Machine import Machine


class ScenarioConfigurationApplier(ABC):
    @abstractmethod
    def apply_to_network_scenario(self, net_scenario: Lab) -> None:
        raise NotImplementedError("You must implement `apply_to_network_scenario` method.")

    @abstractmethod
    def get_device_info(self, net_scenario: Lab) -> dict[Machine, (dict[str, str], str, Callable)]:
        raise NotImplementedError("You must implement `get_device_info` method.")

from abc import ABC, abstractmethod
from typing import Callable

from Kathara.model.Machine import Machine

from .vendor_commands_mixin import VendorCommandsMixin
from .vendor_format_parser_mixin import VendorFormatParserMixin


class VendorDevice(VendorCommandsMixin, VendorFormatParserMixin, ABC):
    @abstractmethod
    def config_apply_to_device(self, device: Machine, config_path: str, image) -> None:
        raise NotImplementedError("You must implement `config_apply_to_device` method.")

    @abstractmethod
    def config_info_for_device(self, device: Machine, config: str) -> (dict[str, str], str, Callable):
        raise NotImplementedError("You must implement `config_info_for_device` method.")

    def config_has_errors(self, stdout: str, stderr: str) -> bool:
        return False

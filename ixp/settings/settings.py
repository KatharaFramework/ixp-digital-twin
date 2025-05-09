from __future__ import annotations

import ipaddress
import json
import os

from ..foundation.exceptions import InstantiationError
from ..globals import PATH_PREFIX

DEFAULT_SETTINGS_PATH: str = os.path.abspath(os.path.join(PATH_PREFIX, "ixp.conf"))


class Settings(object):
    __slots__ = [
        'scenario_name', 'host_interface', 'peering_lan', 'peering_configuration', 'rib_dumps',
        'route_servers', 'rpki', 'quarantine'
    ]

    __instance: Settings = None

    @staticmethod
    def get_instance() -> Settings:
        if Settings.__instance is None:
            Settings()

        return Settings.__instance

    def __init__(self) -> None:
        if Settings.__instance is not None:
            raise InstantiationError("This class is a singleton!")
        else:
            self.scenario_name: str | None = None
            self.host_interface: str | None = None
            self.peering_lan: dict = {}
            self.peering_configuration: dict = {}
            self.rib_dumps: dict = {}
            self.route_servers: dict = {}
            self.rpki: list = []
            self.quarantine: dict = {}

            Settings.__instance = self

    def load_from_disk(self) -> None:
        if not os.path.exists(DEFAULT_SETTINGS_PATH):
            raise FileNotFoundError(f"File `{DEFAULT_SETTINGS_PATH}` not found.")
        else:
            with open(DEFAULT_SETTINGS_PATH, 'r') as settings_file:
                settings = json.load(settings_file)

            for name, value in settings.items():
                if hasattr(self, name):
                    setattr(self, name, value)

        self.peering_lan["4"] = ipaddress.ip_network(self.peering_lan["4"]) if self.peering_lan["4"] else None
        self.peering_lan["6"] = ipaddress.ip_network(self.peering_lan["6"]) if self.peering_lan["6"] else None

        for rs in self.route_servers.values():
            rs["address"] = ipaddress.ip_address(rs["address"])

        for rpki in self.rpki:
            rpki["address"] = ipaddress.ip_address(rpki["address"])

        if self.quarantine["probe_ips"]["4"]:
            self.quarantine["probe_ips"]["4"] = ipaddress.ip_address(self.quarantine["probe_ips"]["4"])
        if self.quarantine["probe_ips"]["6"]:
            self.quarantine["probe_ips"]["6"] = ipaddress.ip_address(self.quarantine["probe_ips"]["6"])

import ipaddress
from typing import Iterator

from ..foundation.exceptions import InstantiationError


class IPv4Pool:
    __slots__ = ['network', 'hosts', 'default_gw']

    def __init__(self, network: str):
        self.network = ipaddress.ip_network(network)
        self.hosts: Iterator = self.network.hosts()
        self.default_gw: ipaddress.IPv4Interface = self.next()

    def next(self) -> ipaddress.IPv4Interface:
        return ipaddress.ip_interface(f"{next(self.hosts)}/{self.network.prefixlen}")


class IPAM:
    __slots__ = ['pools']

    __instance: 'IPAM' = None

    @staticmethod
    def get_instance() -> 'IPAM':
        if IPAM.__instance is None:
            IPAM()

        return IPAM.__instance

    def __init__(self) -> None:
        if IPAM.__instance is not None:
            raise InstantiationError("This class is a singleton!")
        else:
            self.pools: dict[str, IPv4Pool] = {}

            IPAM.__instance = self

    def pool(self, pool: str) -> IPv4Pool:
        if pool not in self.pools:
            self.pools[pool] = IPv4Pool(pool)

        return self.pools[pool]

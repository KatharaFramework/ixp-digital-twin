import ipaddress


class BGPRoute:
    __slots__ = ["network", "as_path"]

    def __init__(self, network: str, as_path: list[str]) -> None:
        self.network: ipaddress.IPv4Network | ipaddress.IPv6Network = ipaddress.ip_network(network)
        self.as_path: list[int] = [int(x) for x in as_path]

    def __hash__(self) -> int:
        return hash(self.network) + hash(tuple(self.as_path))

    def __eq__(self, other: "BGPRoute") -> bool:
        return self.network == other.network and self.as_path == other.as_path

    def __str__(self) -> str:
        return f"BGPRoute (network={self.network}, as_path={self.as_path})"

    def __repr__(self) -> str:
        return str(self)


class BGPPeering:
    __slots__ = ["l2_address", "l3_address"]

    def __init__(self, l2_address: str | None, l3_address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
        self.l2_address: str | None = l2_address
        self.l3_address: ipaddress.IPv4Address | ipaddress.IPv6Address = l3_address

    def __str__(self) -> str:
        return f"BGPPeering (l2_address={self.l2_address}, l3_address={self.l3_address})"

    def __repr__(self) -> str:
        return str(self)


class BGPRouter:
    __slots__ = ["as_num", "router_id", "peerings", "routes"]

    def __init__(self, as_num: int, router_id: int) -> None:
        self.as_num: int = as_num
        self.router_id: int = router_id
        self.peerings: dict[int, set[BGPPeering]] = {4: set(), 6: set()}
        self.routes: dict[int, set[BGPRoute]] = {4: set(), 6: set()}

    def add_peering(self, l2_address: str, l3_address: str) -> None:
        addr = ipaddress.ip_address(l3_address)
        peering = BGPPeering(l2_address, addr)
        self.peerings[addr.version].add(peering)

    def add_route(self, network: str | None, as_path: list[str]) -> None:
        net = ipaddress.ip_network(network)
        self.routes[net.version].add(BGPRoute(network, as_path))

    def has_peering(self, address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        v_peerings = self.peerings[address.version]
        return any([x.l3_address == address for x in v_peerings])

    def get_name(self) -> str:
        return f"as{self.as_num}_{self.router_id}"

    def __str__(self) -> str:
        return f"BGPRouter (router_id={self.router_id}, peerings={self.peerings}, routes={self.routes})"

    def __repr__(self) -> str:
        return str(self)


class BGPNeighbour:
    __slots__ = ["as_num", "routers"]

    def __init__(self, as_num: int) -> None:
        self.as_num: int = as_num
        self.routers: dict[int, BGPRouter] = {}

    def add_router(self, router_id: int) -> BGPRouter:
        self.routers[router_id] = BGPRouter(self.as_num, router_id)
        return self.routers[router_id]

    def __str__(self) -> str:
        return f"BGPNeighbour (as={self.as_num}, routers={self.routers})"

    def __repr__(self) -> str:
        return str(self)

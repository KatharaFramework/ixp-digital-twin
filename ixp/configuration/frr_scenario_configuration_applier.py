import io
import logging

from Kathara.model.Lab import Lab
from Kathara.model.Machine import Machine

from ..foundation.dumps.table_dump.table_dump import TableDump
from ..foundation.configuration.scenario_configuration_applier import (
    ScenarioConfigurationApplier,
)
from ..model.bgp_neighbour import BGPRouter
from ..settings.settings import Settings

# --------------------------- Start of BGP configuration templates -----------------------------------------------

ZEBRA_CONFIG = """hostname frr
password frr
enable password frr"""

BGPD_BASIC_CONFIG = """
router bgp {as_number}
 no bgp default ipv4-unicast
 no bgp ebgp-requires-policy
 no bgp network import-check
{neighbour_config}"""

AS_PATH_ROUTE_MAP = """
ip{v_type} prefix-list FILTER_AS_PATH_V{v}_{i} permit {network}
route-map SET_AS_PATH_V{v} permit {permit_n}
  match ip{v_type} address prefix-list FILTER_AS_PATH_V{v}_{i}
  set as-path prepend {as_path}"""
EMPTY_AS_PATH_ROUTE_MAP = "route-map SET_AS_PATH_V{v} permit {permit_n}"  # Accept everything that does not match
IPV6_ROUTE_MAP = """
route-map PREFER_IPV6_GLOBAL permit 10
  set ipv6 next-hop prefer-global"""

BGPD_NEIGHBOUR_CONFIG = """
 neighbor {ip} remote-as {as_num}
 neighbor {ip} timers connect 10
 neighbor {ip} solo"""

BGPD_AF_BLOCK = """
 address-family ipv{v} unicast
{neighbours_activate}
{networks_announcements}
 exit-address-family"""
BGPD_NEIGHBOUR_ACTIVATE = """  neighbor {ip} activate
  neighbor {ip} maximum-prefix 65536
  neighbor {ip} soft-reconfiguration inbound
{neighbour_route_maps}
"""
BGPD_NEIGHBOUR_AS_PATH_ROUTE_MAP_OUT = "  neighbor {ip} route-map SET_AS_PATH_V{v} out"
BGPD_NEIGHBOR_IPV6_ROUTE_MAP_IN = "  neighbor {ip} route-map PREFER_IPV6_GLOBAL in"

BGPD_NETWORK_ANNOUNCEMENT = "  network {net}"


# ---------------------------  End of BGP configuration templates -----------------------------------------------


class FrrScenarioConfigurationApplier(ScenarioConfigurationApplier):
    __slots__ = ["_table_dump"]

    def __init__(self, table_dump: TableDump) -> None:
        self._table_dump: TableDump = table_dump

    def apply_to_network_scenario(self, net_scenario: Lab) -> None:
        for as_num, neighbour in self._table_dump.entries.items():
            for neigh_router in neighbour.routers.values():
                device_name = f"{as_num}_{neigh_router.router_id}"
                if net_scenario.has_machine(device_name):
                    router: Machine = net_scenario.get_machine(device_name)
                    self._configure_device(router, neigh_router)

    def get_device_info(self, net_scenario: Lab) -> dict[Machine, (dict[str, str], str)]:
        device_info = {}
        for as_num, neighbour in self._table_dump.entries.items():
            for neigh_router in neighbour.routers.values():
                device_name = f"{as_num}_{neigh_router.router_id}"
                if not net_scenario.has_machine(device_name):
                    logging.warning(f"Skipping device `{device_name}` since not in the network scenario...")
                    continue

                logging.info(f'Getting configuration information for device `{device_name}`...')
                device: Machine = net_scenario.get_machine(device_name)

                bgpd_configuration = self._write_device_configuration(neigh_router)
                bgpd_configuration_io = io.StringIO("\n".join(bgpd_configuration))
                device_info[device] = (
                    {"/etc/frr/bgpd.conf": bgpd_configuration_io},
                    "systemctl restart frr",
                    lambda stdout, stderr: False
                )

                logging.info(f"Configuration information retrieved for device `{device_name}`: {device_info[device]}")

        return device_info

    def apply_to_devices(self, devices: dict[str, Machine]) -> None:
        for as_num, neighbour in self._table_dump.entries.items():
            for neigh_router in neighbour.routers.values():
                device_name = f"{as_num}_{neigh_router.router_id}"
                if device_name in devices:
                    router: Machine = devices[device_name]
                    self._configure_device(router, neigh_router)

    def _configure_device(self, device: Machine, router: BGPRouter) -> None:
        logging.info(f"Configuring FRR BGP in device `{device.name}`...")

        device.add_meta("image", "kathara/frr")

        device.create_file_from_list(["zebra=yes", "bgpd=yes"], "/etc/frr/daemons")

        zebra_config = ZEBRA_CONFIG.split("\n")
        device.create_file_from_list(zebra_config, "/etc/frr/zebra.conf")

        bgpd_configuration = self._write_device_configuration(router)
        device.create_file_from_list(bgpd_configuration, "/etc/frr/bgpd.conf")

        with device.lab.fs.open(f"{device.name}.startup", "a") as startup:
            startup.write("systemctl start frr\n")

    @staticmethod
    def _write_device_configuration(router: BGPRouter) -> list[str]:
        bgpd_configuration = ZEBRA_CONFIG.split("\n")

        v_route_maps = {4: 0, 6: 0}
        for v, v_routes in router.routes.items():
            for entry in v_routes:
                if len(entry.as_path) > 1:
                    v_route_maps[v] += 1
                    bgpd_configuration.append(
                        AS_PATH_ROUTE_MAP.format(
                            v=v,
                            v_type="v6" if v == 6 else "",
                            i=v_route_maps[v],
                            permit_n=v_route_maps[v] * 10,
                            as_path=" ".join([str(x) for x in entry.as_path[1:]]),
                            network=entry.network,
                        )
                    )

        for v, n_route_maps in v_route_maps.items():
            if n_route_maps > 0:
                bgpd_configuration.append(
                    EMPTY_AS_PATH_ROUTE_MAP.format(
                        v=v, permit_n=(n_route_maps + 1) * 10
                    )
                )

        if len(router.peerings[6]) > 0:
            bgpd_configuration.append(IPV6_ROUTE_MAP)

        neighbours_configs = "\n".join(
            [
                BGPD_NEIGHBOUR_CONFIG.format(ip=rs["address"], as_num=rs["as_num"])
                for rs in Settings.get_instance().route_servers.values()
            ]
        )

        basic_config = BGPD_BASIC_CONFIG.format(
            as_number=router.as_num, neighbour_config=neighbours_configs
        )
        bgpd_configuration.extend(basic_config.split("\n"))

        for v, peerings in router.peerings.items():
            as_path_v_route_maps = []
            if v_route_maps[v] > 0:
                for rs in filter(
                        lambda x: x["address"].version == v,
                        Settings.get_instance().route_servers.values(),
                ):
                    as_path_v_route_maps.append(
                        BGPD_NEIGHBOUR_AS_PATH_ROUTE_MAP_OUT.format(
                            v=v, ip=rs["address"]
                        )
                    )

            neighbours_activate = "\n".join(
                [
                    BGPD_NEIGHBOUR_ACTIVATE.format(
                        ip=rs["address"],
                        neighbour_route_maps="\n".join(
                            [
                                BGPD_NEIGHBOR_IPV6_ROUTE_MAP_IN.format(ip=rs["address"])
                                if v == 6
                                else ""
                            ]
                        ),
                    )
                    for rs in Settings.get_instance().route_servers.values()
                    if rs["address"].version == v
                ]
                + as_path_v_route_maps
            )

            bgpd_configuration.append(
                BGPD_AF_BLOCK.format(
                    v=v,
                    neighbours_activate=neighbours_activate,
                    networks_announcements="\n".join(
                        [
                            BGPD_NETWORK_ANNOUNCEMENT.format(net=entry.network)
                            for entry in router.routes[v]
                        ]
                    ),
                )
            )

        return bgpd_configuration

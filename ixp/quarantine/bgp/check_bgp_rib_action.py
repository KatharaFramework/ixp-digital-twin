import ipaddress
import logging

from Kathara.manager.Kathara import Kathara
from Kathara.model.Lab import Lab

from ... import utils
from ...foundation.quarantine.action import Action
from ...foundation.quarantine.action_result import SUCCESS, ActionResult, ERROR
from ...model.bgp_neighbour import BGPNeighbour
from ...network_scenario.rs_manager import RouteServerManager
from ...settings.settings import Settings

DEFAULT_NET_V4 = ipaddress.IPv4Network("0.0.0.0/0")
DEFAULT_NET_V6 = ipaddress.IPv6Network("::/0")


class CheckBgpRibAction(Action):
    def verify(
            self, net_scenario: Lab, members: dict[str, BGPNeighbour], rs_manager: RouteServerManager, **kwargs
    ) -> 'ActionResult':
        action_result = ActionResult(self)

        participant_asn = kwargs["asn"]
        participant_ipv4 = kwargs["ipv4"] if "ipv4" in kwargs and kwargs["ipv4"] else None
        participant_ipv6 = kwargs["ipv6"] if "ipv6" in kwargs and kwargs["ipv6"] else None

        rs_routes = {4: {}, 6: {}}
        for rs_name, rs_config in Settings.get_instance().route_servers.items():
            if not net_scenario.has_machine(rs_name):
                logging.warning(f"Skipping RS `{rs_name}` since not in the network scenario...")
                continue

            rs_device = net_scenario.get_machine(rs_name)
            ipv6 = utils.is_device_ipv6(rs_device)

            rs_routes[4 if not ipv6 else 6][rs_name] = set()

            participant_ip = participant_ipv4 if not ipv6 else participant_ipv6
            if participant_ip is None:
                logging.warning(
                    f"Skipping RS `{rs_name}` since no participant IPv{4 if not ipv6 else 6} is specified..."
                )
                continue

            conf = rs_manager.get_config(rs_config["type"])
            cmd = conf.command_neighbor_rib(rs_device, participant_ip)
            (stdout, _, exit_code) = Kathara.get_instance().exec_obj(rs_device, cmd, stream=False)
            if stdout is None or exit_code != 0:
                action_result.add_result(
                    ERROR,
                    f"Error in getting session information for IP {participant_ip} from `{rs_device.name}`.",
                )
                continue

            stdout = stdout.decode("utf-8")
            rib = conf.parse_bgp_neighbor_rib(stdout)

            n_announced_prefixes = len(rib.keys())
            if n_announced_prefixes == 0:
                action_result.add_result(
                    ERROR,
                    f"RIB is empty for IP {participant_ip} from `{rs_device.name}`.",
                )
                continue

            max_rib_prefixes = Settings.get_instance().quarantine["max_rib_prefixes"][f"{participant_ip.version}"]

            if n_announced_prefixes > max_rib_prefixes:
                action_result.add_result(
                    ERROR,
                    f"# advertised prefixes ({n_announced_prefixes}) is more than "
                    f"# maximum prefixes ({max_rib_prefixes}) for IP {participant_ip} from `{rs_device.name}`.",
                )
            else:
                action_result.add_result(
                    SUCCESS,
                    f"{n_announced_prefixes}/{max_rib_prefixes} prefixes announced "
                    f"for IP {participant_ip} from `{rs_device.name}`.",
                )

            v_default_net = DEFAULT_NET_V4 if not ipv6 else DEFAULT_NET_V6

            has_default_route = False
            has_private_prefix = False
            wrong_next_hop = False
            incorrect_as_path = False
            for prefix, next_hops in rib.items():
                if prefix == v_default_net:
                    has_default_route = True
                    action_result.add_result(
                        ERROR,
                        f"IP {participant_ip} announced default route from `{rs_device.name}`.",
                    )

                    continue

                if prefix.is_private:
                    has_private_prefix = True
                    action_result.add_result(
                        ERROR,
                        f"Prefix {prefix} is in the private range "
                        f"for IP {participant_ip} from `{rs_device.name}`.",
                    )
                    continue

                for next_hop, as_paths in next_hops.items():
                    if next_hop != participant_ip:
                        wrong_next_hop = True
                        action_result.add_result(
                            ERROR,
                            f"Prefix {prefix} has {next_hop} as nexthop "
                            f"for IP {participant_ip} from `{rs_device.name}`.",
                        )
                        continue

                    for as_path in as_paths:
                        if participant_asn in as_path and as_path[0] != participant_asn:
                            incorrect_as_path = True
                            action_result.add_result(
                                ERROR,
                                f"Prefix {prefix} has AS Path {as_path} not starting "
                                f"with {participant_asn} from `{rs_device.name}`.",
                            )

                        rs_routes[4 if not ipv6 else 6][rs_name].add((prefix, next_hop, as_path))

            if not has_default_route:
                action_result.add_result(
                    SUCCESS,
                    f"All prefixes are different from the default route from `{rs_device.name}`.",
                )

            if not has_private_prefix:
                action_result.add_result(
                    SUCCESS,
                    f"All prefixes are not in the private range from `{rs_device.name}`.",
                )

            if not wrong_next_hop:
                action_result.add_result(
                    SUCCESS,
                    f"All prefixes have {participant_ip} as nexthop from `{rs_device.name}`.",
                )

            if not incorrect_as_path:
                action_result.add_result(
                    SUCCESS,
                    f"All AS Paths start with {participant_asn} from `{rs_device.name}`.",
                )

        all_equal_routes = True
        for v, v_routes in rs_routes.items():
            rs_names = list(v_routes.keys())
            for rs_name_1 in rs_names:
                for rs_name_2 in rs_names:
                    if rs_name_1 == rs_name_2:
                        continue

                    diff = v_routes[rs_name_1] - v_routes[rs_name_2]
                    if len(diff) > 0:
                        action_result.add_result(
                            ERROR,
                            f"# announced prefixes on `{rs_name_1}` differs from the ones on `{rs_name_2}`.",
                            diff
                        )

                        all_equal_routes = False

        if all_equal_routes:
            action_result.add_result(SUCCESS, f"All RS receive the same announced prefixes.")

        return action_result

    def name(self) -> str:
        return "bgp_rib"

    def display_name(self) -> str:
        return "BGP RIB"

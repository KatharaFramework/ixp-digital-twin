import logging

from Kathara.manager.Kathara import Kathara
from Kathara.model.Lab import Lab

from ... import utils
from ...foundation.quarantine.action import Action
from ...foundation.quarantine.action_result import SUCCESS, ActionResult, ERROR
from ...model.bgp_neighbour import BGPNeighbour
from ...network_scenario.rs_manager import RouteServerManager
from ...settings.settings import Settings


class CheckBgpSessionAction(Action):
    def verify(
            self, net_scenario: Lab, members: dict[str, BGPNeighbour], rs_manager: RouteServerManager, **kwargs
    ) -> 'ActionResult':
        action_result = ActionResult(self)

        participant_asn = kwargs["asn"]
        participant_ipv4 = kwargs["ipv4"] if "ipv4" in kwargs and kwargs["ipv4"] else None
        participant_ipv6 = kwargs["ipv6"] if "ipv6" in kwargs and kwargs["ipv6"] else None

        for rs_name, rs_config in Settings.get_instance().route_servers.items():
            if not net_scenario.has_machine(rs_name):
                logging.warning(f"Skipping RS `{rs_name}` since not in the network scenario...")
                continue

            rs_device = net_scenario.get_machine(rs_name)
            ipv6 = utils.is_device_ipv6(rs_device)

            participant_ip = participant_ipv4 if not ipv6 else participant_ipv6
            if participant_ip is None:
                logging.warning(
                    f"Skipping RS `{rs_name}` since no participant IPv{4 if not ipv6 else 6} is specified..."
                )
                continue

            conf = rs_manager.get_config(rs_config["type"])
            cmd = conf.command_neighbor_info(rs_device, participant_ip)
            (stdout, _, exit_code) = Kathara.get_instance().exec_obj(rs_device, cmd, stream=False)
            if stdout is None or exit_code != 0:
                action_result.add_result(
                    ERROR,
                    f"Error in getting session information for IP {participant_ip} from `{rs_device.name}`.",
                )
                continue

            stdout = stdout.decode("utf-8")
            session_info = conf.parse_bgp_neighbor_state(stdout)

            if session_info["remote_as"] is None:
                action_result.add_result(
                    ERROR,
                    f"Error in getting session information for IP {participant_ip} from `{rs_device.name}`.",
                )
                continue

            if session_info["uptime"] is None:
                action_result.add_result(
                    ERROR,
                    f"BGP Session to AS {participant_asn} is not up "
                    f"for IP {participant_ip} from `{rs_device.name}`.",
                )
                continue

            if session_info["remote_as"] != participant_asn:
                action_result.add_result(
                    ERROR,
                    f"BGP Session established to AS {session_info['remote_as']} instead of AS {participant_asn} "
                    f"for IP {participant_ip} from `{rs_device.name}`.",
                )
                continue

            action_result.add_result(
                SUCCESS,
                f"BGP Session correctly established with AS {participant_asn} "
                f"for IP {participant_ip} from `{rs_device.name}` (uptime: {session_info['uptime']}).",
            )

        return action_result

    def name(self) -> str:
        return "bgp_session"

    def display_name(self) -> str:
        return "BGP Session"

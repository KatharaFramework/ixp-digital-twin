import logging

from Kathara.manager.Kathara import Kathara
from Kathara.model.Lab import Lab

from ... import utils
from ...foundation.quarantine.action import Action
from ...foundation.quarantine.action_result import ActionResult, SUCCESS, ERROR
from ...model.bgp_neighbour import BGPNeighbour
from ...network_scenario.rs_manager import RouteServerManager
from ...regex import PING_LOSS_REGEX
from ...settings.settings import Settings

PING_COUNT = 5


class CheckPingAction(Action):
    def verify(
            self, net_scenario: Lab, members: dict[str, BGPNeighbour], rs_manager: RouteServerManager, **kwargs
    ) -> 'ActionResult':
        action_result = ActionResult(self)

        participant_ipv4 = kwargs["ipv4"] if "ipv4" in kwargs and kwargs["ipv4"] else None
        participant_ipv6 = kwargs["ipv6"] if "ipv6" in kwargs and kwargs["ipv6"] else None

        for rs_name in Settings.get_instance().route_servers.keys():
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

            # Discarded to ensure ARP resolution
            Kathara.get_instance().exec_obj(rs_device, f"ping -c {PING_COUNT} {participant_ip}", stream=False)

            (stdout, _, _) = Kathara.get_instance().exec_obj(
                rs_device, f"ping -c {PING_COUNT} {participant_ip}", stream=False
            )
            stdout = stdout.decode("utf-8")

            matches = PING_LOSS_REGEX.search(stdout)
            if matches:
                loss_percentage = int(matches.group(1))

                if loss_percentage > 0:
                    action_result.add_result(
                        ERROR,
                        f"`{rs_device.name}` is facing loss of {loss_percentage}% to IP {participant_ip}"
                    )
                else:
                    action_result.add_result(
                        SUCCESS,
                        f"`{rs_device.name}` achieved lossless connectivity to IP {participant_ip}"
                    )
            else:
                action_result.add_result(
                    ERROR,
                    f"Error in pinging IP {participant_ip} from `{rs_device.name}`."
                )

        return action_result

    def name(self) -> str:
        return "ping"

    def display_name(self) -> str:
        return "Ping"

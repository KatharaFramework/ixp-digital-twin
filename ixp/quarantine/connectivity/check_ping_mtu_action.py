import logging
import time

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
MAX_MTU = 1500


class CheckPingMtuAction(Action):
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

            stdout_tcpdump = Kathara.get_instance().exec_obj(
                rs_device,
                f"timeout 20 tcpdump -tenni any (icmp or icmp6) and host {participant_ip} -c {PING_COUNT * 2}",
                stream=True
            )

            time.sleep(1)

            payload_size = MAX_MTU - (20 if not ipv6 else 40) - 8  # 1500 - IP - ICMP
            Kathara.get_instance().exec_obj(
                rs_device,
                f"ping -c {PING_COUNT} -M do -s {payload_size} {participant_ip}",
                stream=False
            )

            tcpdump_output = ""
            try:
                while True:
                    (stdout, _) = next(stdout_tcpdump)
                    stdout = stdout.decode('utf-8') if stdout else ""

                    if stdout:
                        tcpdump_output += stdout
            except StopIteration:
                pass

            request_count = 0
            reply_count = 0
            for packet in tcpdump_output.split("\n"):
                if "echo request" in packet:
                    request_count += 1
                if "echo reply" in packet:
                    reply_count += 1

            if request_count == PING_COUNT:
                if request_count == reply_count:
                    action_result.add_result(
                        SUCCESS,
                        f"Link from `{rs_device.name}` to {participant_ip} is able to send {MAX_MTU} bytes packets.",
                    )
                else:
                    action_result.add_result(
                        ERROR,
                        f"Link from `{rs_device.name}` to {participant_ip} is not able to send {MAX_MTU} bytes packets.",
                    )
            else:
                action_result.add_result(
                    ERROR,
                    f"Link from `{rs_device.name}` to {participant_ip} is not able to send {MAX_MTU} bytes packets.",
                )

        return action_result

    def name(self) -> str:
        return "ping_mtu"

    def display_name(self) -> str:
        return "Ping MTU"

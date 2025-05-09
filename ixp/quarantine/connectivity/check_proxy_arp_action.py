import ipaddress
import logging

from Kathara.manager.Kathara import Kathara
from Kathara.model.Lab import Lab

from ... import utils
from ...foundation.quarantine.action import Action
from ...foundation.quarantine.action_result import ActionResult, ERROR, SUCCESS
from ...model.bgp_neighbour import BGPNeighbour
from ...network_scenario.rs_manager import RouteServerManager
from ...settings.settings import Settings

ARPING_COUNT = 5


class CheckProxyArpAction(Action):
    def verify(
            self, net_scenario: Lab, members: dict[str, BGPNeighbour], rs_manager: RouteServerManager, **kwargs
    ) -> 'ActionResult':
        action_result = ActionResult(self)

        participant_mac = kwargs['mac']
        participant_ipv4 = kwargs["ipv4"] if "ipv4" in kwargs and kwargs["ipv4"] else None

        proxy_arp_replies = {}
        for rs_name in Settings.get_instance().route_servers.keys():
            if not net_scenario.has_machine(rs_name):
                logging.warning(f"Skipping RS `{rs_name}` since not in the network scenario...")
                continue

            rs_device = net_scenario.get_machine(rs_name)
            ipv6 = utils.is_device_ipv6(rs_device)

            if ipv6:
                logging.warning(f"Skipping RS `{rs_name}` since it is IPv6...")
            if participant_ipv4 is None:
                logging.warning(f"Skipping RS `{rs_name}` since no participant IPv4 is specified...")
                continue

            for ip in Settings.get_instance().quarantine["proxy_arp_ips"]:
                ip: ipaddress.IPv4Address = ipaddress.ip_address(ip)
                (_, _, exit_code) = Kathara.get_instance().exec_obj(
                    rs_device, f"arping -c {ARPING_COUNT} -t {participant_mac} -i eth0 {ip}", stream=False
                )

                if exit_code == 0:
                    if rs_name not in proxy_arp_replies:
                        proxy_arp_replies[rs_name] = []

                    proxy_arp_replies[rs_name].append(ip)

        success = True
        for rs_name, ips in proxy_arp_replies.items():
            action_result.add_result(
                ERROR,
                f"Candidate router replied to Proxy ARP from "
                f"`{rs_name}` for IPs {', '.join([str(x) for x in ips])}"
            )

            success = False

        if success:
            action_result.add_result(SUCCESS, f"Candidate router does not have Proxy ARP enabled.")

        return action_result

    def name(self) -> str:
        return "proxy_arp"

    def display_name(self) -> str:
        return "Proxy ARP"

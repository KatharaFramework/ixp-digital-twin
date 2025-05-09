import ipaddress
import logging
from typing import Callable

from Kathara.model.Machine import Machine

from ...foundation.configuration.vendor_device import VendorDevice
from ...regex import OPENBGPD_SESSION_REMOTE_AS, OPENBGPD_SESSION_UPTIME, OPENBGPD_RIB_PREFIX, OPENBGPD_RIB_NEXTHOP


class OpenBgpdVendorDevice(VendorDevice):
    def config_apply_to_device(self, device: Machine, config_path: str, image: str) -> None:
        logging.info(f"Configuring OpenBGPD in device `{device.name}`...")
        device.add_meta("image", image)
        device.create_file_from_path(config_path, "/etc/bgpd.conf")

        with device.lab.fs.open(f"{device.name}.startup", "a") as startup:
            startup.write(f"sleep 3\n")
            startup.write("systemctl start openbgpd\n")

    def config_info_for_device(self, device: Machine, config: str) -> (dict[str, str], str, Callable):
        return {"/etc/bgpd.conf": config}, self.command_config_reload(device), self.config_has_errors

    def config_has_errors(self, stdout: str, stderr: str) -> bool:
        return "config file has errors" in stdout

    def command_config_reload(self, device: Machine) -> str:
        return "/usr/sbin/bgpctl reload"

    def command_neighbor_info(
            self, device: Machine, session_ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> str:
        return f"/usr/sbin/bgpctl show neighbor {session_ip}"

    def command_neighbor_rib(
            self, device: Machine, session_ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> str:
        return f"/usr/sbin/bgpctl show rib in detail neighbor {session_ip}"

    def parse_bgp_neighbor_state(self, bgp_output: str) -> dict:
        matches = OPENBGPD_SESSION_REMOTE_AS.search(bgp_output)
        remote_as = matches.group(1) if matches else None

        matches = OPENBGPD_SESSION_UPTIME.search(bgp_output)
        uptime = matches.group(1) if matches else None

        return {"remote_as": int(remote_as) if remote_as else None, "uptime": uptime}

    def parse_bgp_neighbor_rib(self, bgp_output: str) -> dict:
        entries = bgp_output.strip().split("\n\n")
        rib = {}

        for entry in entries:
            prefix_match = OPENBGPD_RIB_PREFIX.search(entry)
            nexthop_match = OPENBGPD_RIB_NEXTHOP.search(entry)

            lines = entry.split("\n")
            as_number_line = lines[1].strip()  # First line is the AS Path
            as_path = tuple(map(int, as_number_line.split()))  # Use tuples since they are hashable in set

            prefix = ipaddress.ip_network(prefix_match.group(1)) if prefix_match else None
            nexthop = ipaddress.ip_address(nexthop_match.group(1)) if nexthop_match else None

            if prefix not in rib:
                rib[prefix] = {}
            if nexthop not in rib[prefix]:
                rib[prefix][nexthop] = set()

            rib[prefix][nexthop].add(as_path)

        return rib

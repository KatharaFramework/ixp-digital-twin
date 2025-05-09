import ipaddress
import logging
import os
from datetime import datetime
from typing import Callable

from Kathara.model.Machine import Machine

from ... import utils
from ...foundation.configuration.vendor_device import VendorDevice
from ...regex import BIRD_SESSION_REMOTE_AS, BIRD_SESSION_UPTIME, BIRD_RIB_NEXTHOP, BIRD_RIB_PREFIX, BIRD_RIB_AS_PATH


class BirdVendorDevice(VendorDevice):
    def config_apply_to_device(self, device: Machine, config_path: str, image: str) -> None:
        logging.info(f"Configuring BIRD in device `{device.name}`...")
        device.add_meta("image", image)
        bird_bin = self.get_bird_bin(device)
        if os.path.isdir(config_path):
            device.copy_directory_from_path(config_path, f"/etc/bird/")
        else:
            device.create_file_from_path(config_path, f"/etc/bird/{bird_bin}.conf")

        with device.lab.fs.open(f"{device.name}.startup", "a") as startup:
            startup.write("mkdir -p /usr/local/var/log\n")
            startup.write("chown bird:bird /usr/local/var/log\n")
            startup.write(f"sleep 3\n")
            startup.write(f"/etc/init.d/{bird_bin} start\n")

    def config_info_for_device(self, device: Machine, config: str) -> (dict[str, str], str, Callable):
        bird_bin = self.get_bird_bin(device)
        bird_config_is_dir = os.path.isdir(config)
        bird_config_folder = f"/etc/bird"
        if not bird_config_is_dir:
            config_src2dst = {f"{bird_config_folder}/{bird_bin}.conf": config}
        else:
            config_src2dst = {}

            abs_config_path = os.path.join(os.path.abspath(config), "")
            for root, _, files in os.walk(abs_config_path):
                for file in files:
                    conf_rel_path = root.replace(abs_config_path, '')
                    src_path = os.path.join(root, file)
                    dst_path = f"{bird_config_folder}/{conf_rel_path + '/' if conf_rel_path else ''}{file}"
                    config_src2dst[dst_path] = src_path

        return config_src2dst, self.command_config_reload(device), self.config_has_errors

    def command_config_reload(self, device: Machine) -> str:
        bird_bin = self.get_bird_bin(device)
        birdc_bin = self.get_birdc_bin(device)

        bird_config = f"/etc/bird/{bird_bin}.conf"
        return f'/bin/bash -c "{birdc_bin} <<< \'configure soft \\"{bird_config}\\"\'"'

    def command_neighbor_info(
            self, device: Machine, session_ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> str:
        bird_bin = self.get_birdc_bin(device)
        return (f'/bin/bash -c "name=$({bird_bin} \\"show protocols all\\" | '
                f'awk \'BEGIN{{RS = \\"\\n\\n\\"}} /Neighbor address: {session_ip}\\n/ {{print $1}}\'); '
                f'{bird_bin} \\"show protocols all $name\\" | tail -n +2"')

    def command_neighbor_rib(
            self, device: Machine, session_ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> str:
        bird_bin = self.get_birdc_bin(device)
        return (f'/bin/bash -c "name=$({bird_bin} \\"show protocols all\\" | '
                f'awk \'BEGIN{{RS = \\"\\n\\n\\"}} /Neighbor address: {session_ip}\\n/ {{print $1}}\'); '
                f'{bird_bin} \\"show route protocol $name all\\" | tail -n +2"')

    def parse_bgp_neighbor_state(self, bgp_output: str) -> dict:
        matches = BIRD_SESSION_REMOTE_AS.search(bgp_output)
        remote_as = matches.group(1) if matches else None

        matches = BIRD_SESSION_UPTIME.search(bgp_output)
        uptime = (
            datetime.now() - datetime.strptime(matches.group(1).strip(), "%Y-%m-%d %H:%M:%S")
            if matches else None
        )

        return {"remote_as": int(remote_as) if remote_as else None, "uptime": uptime}

    def parse_bgp_neighbor_rib(self, bgp_output: str) -> dict:
        entries = bgp_output.strip().split("BGP.local_pref:")
        rib = {}

        for entry in entries[:-1]:
            prefix_match = BIRD_RIB_PREFIX.search(entry)
            nexthop_match = BIRD_RIB_NEXTHOP.search(entry)

            matches = BIRD_RIB_AS_PATH.search(entry)
            as_path = tuple()
            if matches:
                as_path = tuple(map(int, matches.group(1).strip().split()))  # Use tuples since they are hashable in set

            prefix = ipaddress.ip_network(prefix_match.group(1)) if prefix_match else None
            nexthop = ipaddress.ip_address(nexthop_match.group(1)) if nexthop_match else None

            if prefix is None or nexthop is None:
                continue

            if prefix not in rib:
                rib[prefix] = {}
            if nexthop not in rib[prefix]:
                rib[prefix][nexthop] = set()

            rib[prefix][nexthop].add(as_path)

        return rib

    @staticmethod
    def get_bird_bin(device: Machine) -> str:
        return "bird" if "bird2" in device.get_image() or "bird3" in device.get_image() else \
            "bird6" if utils.is_device_ipv6(device) else "bird"

    @staticmethod
    def get_birdc_bin(device: Machine) -> str:
        return "birdc" if "bird2" in device.get_image() or "bird3" in device.get_image() else \
            "birdc6" if utils.is_device_ipv6(device) else "birdc"

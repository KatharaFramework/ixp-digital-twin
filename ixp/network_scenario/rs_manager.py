import logging
import os
from typing import Callable

from Kathara.model.Lab import Lab
from Kathara.model.Machine import Machine

from ..foundation.configuration.scenario_configuration_applier import ScenarioConfigurationApplier
from ..foundation.configuration.vendor_device import VendorDevice
from ..globals import RESOURCES_FOLDER, L2_FABRIC_CD_NAME, BACKBONE_CD_NAME, BACKBONE_IP_PREFIX
from ..model.collision_domain import CollisionDomain
from ..model.ipam import IPAM, IPv4Pool
from ..settings.settings import Settings
from ..utils import class_for_name


class RouteServerManager(ScenarioConfigurationApplier):
    __slots__ = ["_configurations", "_ip_pool"]

    def __init__(self) -> None:
        self._configurations: dict[str, VendorDevice] = {}
        self._ip_pool: IPv4Pool = IPAM.get_instance().pool(BACKBONE_IP_PREFIX)

    def apply_to_network_scenario(self, net_scenario: Lab) -> None:
        for name, rs in Settings.get_instance().route_servers.items():
            ip_v = rs["address"].version

            rs_device = net_scenario.new_machine(name)
            rs_device.add_meta("ipv6", ip_v == 6)
            rs_device.add_meta("sysctl", "net.ipv4.tcp_rmem=33554432")
            rs_device.add_meta("sysctl", "net.ipv4.tcp_wmem=33554432")
            cd = CollisionDomain.get_instance().get(rs_device.name, L2_FABRIC_CD_NAME)
            net_scenario.connect_machine_obj_to_link(rs_device, cd)

            v_peering_lan = Settings.get_instance().peering_lan[f"{ip_v}"]
            net_scenario.create_file_from_string(
                f"ip address add {rs['address']}/{v_peering_lan.prefixlen} dev eth0\n",
                f"{name}.startup",
            )

            if len(Settings.get_instance().rpki) > 0:
                self.connect_backbone(rs_device)

            conf = self.get_config(rs["type"])
            conf.config_apply_to_device(rs_device, os.path.join(RESOURCES_FOLDER, rs["config"]), rs['image'])

            logging.success(f"Device `{name}` created.")

    def connect_backbone(self, rs_device: Machine) -> None:
        net_scenario = rs_device.lab
        iface_num = net_scenario.connect_machine_obj_to_link(rs_device, BACKBONE_CD_NAME).num
        backbone_ip_addr = self._ip_pool.next()

        logging.info(f"Connecting `{rs_device.name}` to backbone with IP={backbone_ip_addr}...")

        net_scenario.update_startup_file_from_string(
            rs_device,
            f"ip address add {backbone_ip_addr} dev eth{iface_num}\n"
            f"ip route add default via {self._ip_pool.default_gw.ip}\n",
        )

    def get_device_info(self, net_scenario: Lab) -> dict[Machine, (dict[str, str], str, Callable)]:
        device_info = {}
        for name, rs in Settings.get_instance().route_servers.items():
            if not net_scenario.has_machine(name):
                logging.warning(f"Skipping device `{rs['name']}` since not in the network scenario...")
                continue

            logging.info(f'Getting configuration information for device `{name}`...')
            device = net_scenario.get_machine(name)

            conf = self.get_config(rs["type"])
            info = conf.config_info_for_device(device, os.path.join(RESOURCES_FOLDER, rs["config"]))

            device_info[device] = info

            logging.info(f"Configuration information retrieved for device `{name}`: {info}")

        return device_info

    def get_config(self, config_name: str) -> VendorDevice:
        if config_name not in self._configurations:
            module_name = "ixp.configuration.rs"
            class_name = f"{config_name}_vendor_device"

            self._configurations[config_name] = class_for_name(module_name, class_name)()

        return self._configurations[config_name]

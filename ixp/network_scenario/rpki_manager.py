import logging
from typing import Callable

from Kathara.model.Lab import Lab
from Kathara.model.Machine import Machine

from ..foundation.configuration.scenario_configuration_applier import ScenarioConfigurationApplier
from ..globals import BACKBONE_CD_NAME, GATEWAY_DEVICE_NAME, BACKBONE_IP_PREFIX
from ..model.ipam import IPAM, IPv4Pool
from ..settings.settings import Settings


class RPKIManager(ScenarioConfigurationApplier):
    __slots__ = ["_ip_pool"]

    def __init__(self) -> None:
        self._ip_pool: IPv4Pool = IPAM.get_instance().pool(BACKBONE_IP_PREFIX)

    def apply_to_network_scenario(self, net_scenario: Lab) -> None:
        for idx, rpki in enumerate(Settings.get_instance().rpki):
            if rpki["type"] == "external":
                self._apply_external(net_scenario, rpki)
            elif rpki["type"] == "internal":
                raise NotImplementedError("RPKI type `internal` is not implemented`")
            else:
                raise Exception(f"Unknown RPKI type: {rpki['type']}")

    def _apply_external(self, net_scenario: Lab, rpki: dict) -> None:
        if not net_scenario.has_machine(GATEWAY_DEVICE_NAME):
            gateway_device = self._create_gateway_device(net_scenario)
        else:
            gateway_device = net_scenario.get_machine(GATEWAY_DEVICE_NAME)

        logging.info(f"Allowing RPKI traffic to {rpki['address']}:{rpki['port']}/{rpki['protocol']}...")

        cmd = self._get_external_command(rpki)
        net_scenario.update_startup_file_from_string(gateway_device, f"{cmd}\n")

    def _create_gateway_device(self, net_scenario: Lab) -> Machine:
        gateway_device = net_scenario.new_machine(GATEWAY_DEVICE_NAME)
        net_scenario.connect_machine_obj_to_link(gateway_device, BACKBONE_CD_NAME)

        gateway_device.add_meta("bridged", True)

        net_scenario.create_startup_file_from_string(
            gateway_device,
            f"ip address add {self._ip_pool.default_gw} dev eth0\n"
            f"iptables -t nat -A POSTROUTING -s {self._ip_pool.network} -o eth1 -j MASQUERADE\n"
            "iptables -P FORWARD DROP\n"
        )

        logging.info(f"Created device `{GATEWAY_DEVICE_NAME}` with IP={self._ip_pool.default_gw}...")

        return gateway_device

    def _get_external_command(self, rpki: dict) -> str:
        return (
            f"iptables -A FORWARD -s {self._ip_pool.network} -d {rpki['address']} -p {rpki['protocol']} --dport {rpki['port']} -j ACCEPT; "
            f"iptables -A FORWARD -s {rpki['address']} -d {self._ip_pool.network} -p {rpki['protocol']} --sport {rpki['port']} -j ACCEPT"
        )

    def get_device_info(self, net_scenario: Lab) -> dict[Machine, (dict[str, str], str, Callable)]:
        device_info = {}
        external_cmds = []
        for idx, rpki in enumerate(Settings.get_instance().rpki):
            if rpki["type"] == "external":
                external_cmds.append(self._get_external_command(rpki))
            elif rpki["type"] == "internal":
                raise NotImplementedError("RPKI type `internal` is not implemented`")
            else:
                raise Exception(f"Unknown RPKI type: {rpki['type']}")

        if external_cmds:
            if not net_scenario.has_machine(GATEWAY_DEVICE_NAME):
                logging.warning(
                    f"Skipping updating `external` RPKI since {GATEWAY_DEVICE_NAME} is not in the network scenario..."
                )

            gateway_device = net_scenario.get_machine(GATEWAY_DEVICE_NAME)

            external_cmds_str = "; ".join(external_cmds)
            device_info[gateway_device] = (
                {},
                f'/bin/bash -c "iptables -F; {external_cmds_str}"',
                lambda x, y: False
            )

        return device_info

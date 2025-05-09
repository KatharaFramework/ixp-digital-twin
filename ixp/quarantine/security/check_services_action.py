import ipaddress
import logging
import shlex

import docker
from Kathara.manager.Kathara import Kathara
from Kathara.model.Lab import Lab
from Kathara.model.Machine import Machine
from docker.errors import ImageNotFound

from ... import utils
from ...foundation.quarantine.action import Action
from ...foundation.quarantine.action_result import ActionResult, ERROR, SUCCESS
from ...globals import BIN_FOLDER, SWITCH_DEVICE_NAME
from ...model.bgp_neighbour import BGPNeighbour
from ...model.collision_domain import CollisionDomain
from ...network_scenario.rs_manager import RouteServerManager
from ...settings.settings import Settings

PROBE_DOCKERFILE_NAME = "probe.Dockerfile"
PROBE_IMAGE_NAME = "ixp/probe"
PROBE_DEVICE_NAME = "ixp_probe"


class CheckServicesAction(Action):
    def verify(
            self, net_scenario: Lab, members: dict[str, BGPNeighbour], rs_manager: RouteServerManager, **kwargs
    ) -> 'ActionResult':
        action_result = ActionResult(self)

        try:
            self._check_and_build_image()
        except docker.errors.BuildError as e:
            action_result.add_result(ERROR, "Error while building Docker image.", str(e))
            return action_result

        participant_ipv4 = kwargs["ipv4"] if "ipv4" in kwargs and kwargs["ipv4"] else None
        participant_ipv6 = kwargs["ipv6"] if "ipv6" in kwargs and kwargs["ipv6"] else None

        for rs_name in Settings.get_instance().route_servers.keys():
            if not net_scenario.has_machine(rs_name):
                logging.warning(f"Skipping RS `{rs_name}` since not in the network scenario...")
                continue

            rs_device = net_scenario.get_machine(rs_name)
            ipv6 = utils.is_device_ipv6(rs_device)

            cd = CollisionDomain.get_instance().get(rs_device.name, SWITCH_DEVICE_NAME)
            participant_ip = participant_ipv4 if not ipv6 else participant_ipv6
            if participant_ip is None:
                logging.warning(
                    f"Skipping RS `{rs_name}` since no participant IPv{4 if not ipv6 else 6} is specified..."
                )
                continue

            probe_ip = Settings.get_instance().quarantine["probe_ips"][f"{participant_ip.version}"]
            if probe_ip is None:
                logging.warning(
                    f"Skipping RS `{rs_name}` since no probe IPv{participant_ip.version} is specified..."
                )
                continue
            peering_lan = Settings.get_instance().peering_lan[f"{participant_ip.version}"]
            if peering_lan is None:
                logging.warning(
                    f"Skipping RS `{rs_name}` since no peering IPv{participant_ip.version} LAN is specified..."
                )
                continue

            probe_iface = ipaddress.ip_interface(f"{probe_ip}/{peering_lan.prefixlen}")
            probe_device = self._deploy_probe_device(net_scenario, cd, probe_iface)

            (dns_passed, dns_output) = self._check_dns_service(probe_device, participant_ip)
            if dns_passed:
                action_result.add_result(SUCCESS, f"DNS not responding on IP {participant_ip}.")
            else:
                action_result.add_result(ERROR, f"DNS responding on IP {participant_ip}.", dns_output)

            (ntp_passed, ntp_output) = self._check_ntp_service(probe_device, participant_ip)
            if ntp_passed:
                action_result.add_result(SUCCESS, f"NTP not responding on IP {participant_ip}.")
            else:
                action_result.add_result(ERROR, f"NTP responding on IP {participant_ip}.", ntp_output)

            (snmp_passed, snmp_output) = self._check_snmp_service(probe_device, participant_ip)
            if snmp_passed:
                action_result.add_result(SUCCESS, f"SNMP not responding on IP {participant_ip}.")
            else:
                action_result.add_result(ERROR, f"SNMP responding on IP {participant_ip}.", snmp_output)

        return action_result

    def clean(
            self, net_scenario: Lab, members: dict[str, BGPNeighbour], rs_manager: RouteServerManager, **kwargs
    ) -> None:
        if net_scenario.has_machine(PROBE_DEVICE_NAME):
            probe_device = net_scenario.get_machine(PROBE_DEVICE_NAME)
            self._undeploy_probe_device(probe_device)

    @staticmethod
    def _check_and_build_image() -> None:
        client = docker.from_env()

        logging.debug(f"Checking if image `{PROBE_IMAGE_NAME}` exists...")
        try:
            client.images.get(PROBE_IMAGE_NAME)
            logging.debug(f"Image `{PROBE_IMAGE_NAME}` exists!")
        except ImageNotFound:
            logging.debug(f"Image `{PROBE_IMAGE_NAME}` does not exist, building...")
            client.images.build(
                path=BIN_FOLDER,
                dockerfile=PROBE_DOCKERFILE_NAME,
                tag=PROBE_IMAGE_NAME,
                quiet=True,
                pull=False,
                forcerm=True
            )

    @staticmethod
    def _deploy_probe_device(
            net_scenario: Lab, cd: str, iface_ip: ipaddress.IPv4Interface | ipaddress.IPv6Interface
    ) -> Machine:
        logging.info(f"Deploying probe device in collision domain {cd} and with IP={iface_ip}...")

        if net_scenario.has_machine(PROBE_DEVICE_NAME):
            del net_scenario.machines[PROBE_DEVICE_NAME]
            if net_scenario.fs.exists(f"{PROBE_DEVICE_NAME}.startup"):
                net_scenario.fs.remove(f"{PROBE_DEVICE_NAME}.startup")

        probe_device = net_scenario.get_or_new_machine(PROBE_DEVICE_NAME, image=PROBE_IMAGE_NAME)
        probe_device.add_meta("ipv6", iface_ip.version == 6)

        probe_cd = net_scenario.get_link(cd)
        if PROBE_DEVICE_NAME in probe_cd.machines:
            del probe_cd.machines[PROBE_DEVICE_NAME]
        probe_device.add_interface(probe_cd)

        net_scenario.create_file_from_string(
            f"ip addr add {iface_ip} dev eth0",
            f"{probe_device.name}.startup",
        )

        Kathara.get_instance().undeploy_machine(probe_device)
        Kathara.get_instance().deploy_machine(probe_device)

        return probe_device

    @staticmethod
    def _undeploy_probe_device(probe_device: Machine) -> None:
        logging.info(f"Undeploying probe device `{probe_device.name}`...")

        net_scenario = probe_device.lab

        Kathara.get_instance().undeploy_machine(probe_device)

        del net_scenario.machines[probe_device.name]

        net_scenario.fs.remove(f"{probe_device.name}.startup")

        logging.info(f"Probe device `{probe_device.name}` undeployed...")

    @staticmethod
    def _check_dns_service(
            probe_device: Machine,
            participant_ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> (bool, str | None):
        dns_name = Settings.get_instance().quarantine["dns_name"]
        logging.info(f"Checking if DNS is replying to query `{dns_name}` on participant IP `{participant_ip}`...")

        (stdout, _, exitcode) = Kathara.get_instance().exec_obj(
            probe_device,
            shlex.split(f"dig @{participant_ip} {dns_name}"),
            stream=False
        )
        stdout = stdout.decode("utf-8") if stdout else None

        if exitcode != 0:
            return True, None

        return False, stdout

    @staticmethod
    def _check_ntp_service(
            probe_device: Machine,
            participant_ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> (bool, str | None):
        logging.info(f"Checking if NTP is active on participant IP `{participant_ip}`...")

        (stdout, stderr, exitcode) = Kathara.get_instance().exec_obj(
            probe_device,
            shlex.split(f"ntpq -c rv {participant_ip}"),
            stream=False
        )
        stdout = stdout.decode("utf-8") if stdout else None
        stderr = stderr.decode("utf-8") if stderr else None

        if (stdout is None and
                (stderr is not None and ("socket error" in stderr.lower() or "timed out" in stderr.lower()))):
            return True, None

        return False, stdout

    @staticmethod
    def _check_snmp_service(
            probe_device: Machine,
            participant_ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> (bool, str | None):
        logging.info(f"Checking if SNMP is active on participant IP `{participant_ip}`...")

        (stdout, _, exitcode) = Kathara.get_instance().exec_obj(
            probe_device,
            shlex.split(f"snmpwalk {participant_ip}"),
            stream=False
        )
        stdout = stdout.decode("utf-8") if stdout else None

        if exitcode == 1:
            return True, None

        return False, stdout

    def name(self) -> str:
        return "services"

    def display_name(self) -> str:
        return "Running Services"

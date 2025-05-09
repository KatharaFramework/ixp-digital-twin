import ipaddress
import json
import logging
import os
import shlex
import time
from io import BytesIO

from Kathara.foundation.manager.exec_stream.IExecStream import IExecStream
from Kathara.manager.Kathara import Kathara
from Kathara.model.Lab import Lab
from Kathara.model.Machine import Machine

from ... import utils
from ...foundation.quarantine.action import Action
from ...foundation.quarantine.action_result import ActionResult, SUCCESS, ERROR
from ...globals import BIN_FOLDER
from ...model.bgp_neighbour import BGPNeighbour
from ...network_scenario.rs_manager import RouteServerManager
from ...settings.settings import Settings


class CheckTrafficAction(Action):
    def verify(
            self, net_scenario: Lab, members: dict[str, BGPNeighbour], rs_manager: RouteServerManager, **kwargs
    ) -> 'ActionResult':
        action_result = ActionResult(self)

        participant_asn = kwargs['asn']
        participant_mac = kwargs['mac']
        participant_ipv4 = kwargs['ipv4'] if "ipv4" in kwargs and kwargs["ipv4"] else None
        participant_ipv6 = kwargs['ipv6'] if "ipv6" in kwargs and kwargs["ipv6"] else None

        # Build MAC Address set
        all_macs = set([
            peering.l2_address
            for neighbor in members.values()
            if neighbor.as_num != participant_asn
            for router in neighbor.routers.values()
            for v_peering in router.peerings.values()
            for peering in v_peering
        ])
        # Just to be sure, filter the participant MAC
        all_macs = all_macs - {participant_mac}

        streams = {}
        for rs_name in Settings.get_instance().route_servers.keys():
            if not net_scenario.has_machine(rs_name):
                logging.warning(f"Skipping RS `{rs_name}` since not in the network scenario...")
                continue

            rs_device = net_scenario.get_machine(rs_name)
            ipv6 = utils.is_device_ipv6(rs_device)

            logging.info(f"Copying traffic dumper script into RS `{rs_name}`...")
            with open(os.path.join(BIN_FOLDER, "traffic_dump.py"), "rb") as py_script:
                content = BytesIO(py_script.read())
            Kathara.get_instance().copy_files(rs_device, {'/traffic_dump.py': content})

            participant_ip = participant_ipv4 if not ipv6 else participant_ipv6
            if participant_ip is None:
                logging.warning(
                    f"Skipping RS `{rs_name}` since no participant IPv{4 if not ipv6 else 6} is specified..."
                )
                continue

            streams[rs_name] = self._start_device_dumper(rs_device, all_macs, participant_mac, participant_ip)

        results = {}
        for name, stream in streams.items():
            result = ""
            while True:
                time.sleep(1)
                try:
                    (line, _) = next(stream)
                    if line:
                        result += line.decode('utf-8').strip()
                except StopIteration:
                    break

            results[name] = json.loads(result)

        for name in streams.keys():
            logging.info(f"Deleting traffic dumper script from RS `{name}`...")
            Kathara.get_instance().exec(name, "rm -Rf /traffic_dump.py", lab=net_scenario, stream=False)

        for name, result in results.items():
            if len(result) > 0:
                action_result.add_result(ERROR, f"Unauthorized traffic on `{name}`.", "\n".join(result))
            else:
                action_result.add_result(SUCCESS, f"No unauthorized traffic on `{name}`.")

        return action_result

    def clean(
            self, net_scenario: Lab, members: dict[str, BGPNeighbour], rs_manager: RouteServerManager, **kwargs
    ) -> None:
        for rs_name in Settings.get_instance().route_servers.keys():
            logging.info(f"Killing traffic dumper script from RS `{rs_name}`...")
            (_, _, exit_code) = Kathara.get_instance().exec(
                rs_name, "pkill -f -i traffic_dump.py", lab=net_scenario, stream=False
            )
            logging.info(f"Killed traffic dumper script with exit code: {exit_code}.")

            logging.info(f"Deleting traffic dumper script from RS `{rs_name}`...")
            (_, _, exit_code) = Kathara.get_instance().exec(
                rs_name, "rm -Rf /traffic_dump.py", lab=net_scenario, stream=False
            )
            logging.info(f"Deleted traffic dumper with exit code: {exit_code}.")

    @staticmethod
    def _start_device_dumper(
            rs_device: Machine, all_macs: set, participant_mac: str,
            participant_ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> IExecStream:
        sniff_time = Settings.get_instance().quarantine["traffic_dump_mins"] * 60
        logging.info(f"Start traffic dump for {sniff_time}s with MAC={participant_mac} and IP={participant_ip}...")

        v = participant_ip.version
        macs_str = ",".join(all_macs)
        cmd = f"/usr/bin/python3 /traffic_dump.py eth0 {sniff_time} {macs_str} {participant_mac} {participant_ip} {v}"
        logging.debug(f"Running cmd `{cmd}`")

        return Kathara.get_instance().exec_obj(machine=rs_device, command=shlex.split(cmd))

    def name(self) -> str:
        return "traffic"

    def display_name(self) -> str:
        return "Unauthorized Traffic"

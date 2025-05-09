import argparse
import ipaddress
import logging
import os
import re

from Kathara.setting.Setting import Setting

from ixp.colored_logging import set_logging
from ixp.foundation.dumps.member_dump.member_dump_factory import MemberDumpFactory
from ixp.foundation.quarantine.action_result import WARNING
from ixp.globals import RESOURCES_FOLDER
from ixp.network_scenario.network_scenario_manager import NetworkScenarioManager
from ixp.quarantine.action_manager import ActionManager
from ixp.settings.settings import Settings

MAC_ADDRESS_REGEX = re.compile(r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$")


def mac_address(mac_str: str) -> str:
    if not MAC_ADDRESS_REGEX.match(mac_str):
        raise ValueError

    return mac_str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--asn', type=int, required=True)
    parser.add_argument('--mac', type=mac_address, required=True)
    parser.add_argument('--ipv4', type=ipaddress.IPv4Address, required=False)
    parser.add_argument('--ipv6', type=ipaddress.IPv6Address, required=False)
    parser.add_argument('--exclude_checks', type=str, required=False, default="")
    parser.add_argument('--result-level', type=int, required=False, default=WARNING)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    set_logging()

    settings = Settings.get_instance()
    settings.load_from_disk()

    Setting.get_instance().load_from_dict({"manager_type": "docker"})

    member_dump_class = MemberDumpFactory().get_class_from_name(settings.peering_configuration["type"])
    entries = member_dump_class().load_from_file(os.path.join(RESOURCES_FOLDER, settings.peering_configuration["path"]))

    net_scenario_manager = NetworkScenarioManager()
    net_scenario = net_scenario_manager.get()
    if len(net_scenario.machines) <= 0:
        logging.error(f"Network Scenario `{net_scenario.name}` is not started!")
        exit(1)

    action_manager = ActionManager(exclude=args.exclude_checks.split(','))
    kwargs = {k: v for k, v in vars(args).items()}
    results = action_manager.check(net_scenario, entries, **kwargs)
    all_passed = all([x.passed() for x in results])

    for result in results:
        result.print(level=args.result_level)

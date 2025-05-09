import argparse
import os

from Kathara.setting.Setting import Setting

from ixp.colored_logging import set_logging
from ixp.configuration.frr_scenario_configuration_applier import FrrScenarioConfigurationApplier
from ixp.foundation.dumps.member_dump.member_dump_factory import MemberDumpFactory
from ixp.foundation.dumps.table_dump.table_dump_factory import TableDumpFactory
from ixp.globals import RESOURCES_FOLDER
from ixp.network_scenario.network_scenario_manager import NetworkScenarioManager
from ixp.network_scenario.rpki_manager import RPKIManager
from ixp.network_scenario.rs_manager import RouteServerManager
from ixp.settings.settings import Settings

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--max-devices',
        dest='max_devices',
        type=int,
        required=False,
        help='Limit the number of devices to start.'
    )
    args = parser.parse_args()

    set_logging()

    settings = Settings.get_instance()
    settings.load_from_disk()

    Setting.get_instance().load_from_dict({"manager_type": "docker"})

    member_dump_class = MemberDumpFactory().get_class_from_name(settings.peering_configuration["type"])
    entries = member_dump_class().load_from_file(os.path.join(RESOURCES_FOLDER, settings.peering_configuration["path"]))

    table_dump = TableDumpFactory().get_class_from_name(settings.rib_dumps["type"])(entries)

    for v, file in settings.rib_dumps["dumps"].items():
        table_dump.load_from_file(os.path.join(RESOURCES_FOLDER, file))

    if args.max_devices is not None:
        table_dump.entries = dict(list(table_dump.entries.items())[0:args.max_devices])

    net_scenario_manager = NetworkScenarioManager()
    frr_conf = FrrScenarioConfigurationApplier(table_dump)
    rs_manager = RouteServerManager()
    rpki_manager = RPKIManager()

    net_scenario = net_scenario_manager.build(table_dump)
    frr_conf.apply_to_network_scenario(net_scenario)
    rs_manager.apply_to_network_scenario(net_scenario)
    rpki_manager.apply_to_network_scenario(net_scenario)

    net_scenario_manager.interconnect(table_dump)

    net_scenario_manager.undeploy()
    net_scenario_manager.deploy_chunks()

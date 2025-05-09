import argparse
import logging
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
        '--rs-only',
        dest='rs_only',
        required=False,
        action='store_true',
        help='Reload only RS configurations, skipping peerings.'
    )
    parser.add_argument(
        '--max-devices',
        dest='max_devices',
        type=int,
        required=False,
        help='Limit the number of devices to reload.'
    )
    args = parser.parse_args()

    set_logging()

    if args.rs_only:
        logging.warning("Reloading RS configurations only! Peerings will not be updated!")

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
    if not args.rs_only:
        net_scenario = net_scenario_manager.build_diff(table_dump)
        new_devices = dict(x for x in net_scenario.machines.items() if "new" in x[1].meta and x[1].meta["new"])
        del_devices = dict(x for x in net_scenario.machines.items() if "del" in x[1].meta and x[1].meta["del"])
        frr_conf.apply_to_devices(new_devices)

        net_scenario_manager.deploy_devices(new_devices)
        net_scenario_manager.undeploy_devices(del_devices)
        net_scenario_manager.update_interconnection(table_dump, new_devices, set(del_devices.keys()))
    else:
        net_scenario = net_scenario_manager.get()

    # Update RS configurations
    rs_manager = RouteServerManager()
    rs_info = rs_manager.get_device_info(net_scenario)
    return_code = net_scenario_manager.copy_and_exec_by_device_info(rs_info)
    if return_code != 0:
        exit(1)

    # Update RPKI configurations
    rpki_manager = RPKIManager()
    rpki_info = rpki_manager.get_device_info(net_scenario)
    return_code = net_scenario_manager.copy_and_exec_by_device_info(rpki_info)
    if return_code != 0:
        exit(1)

    if not args.rs_only:
        # Update peerings configurations
        peerings_info = frr_conf.get_device_info(net_scenario)
        return_code = net_scenario_manager.copy_and_exec_by_device_info(peerings_info)
        if return_code != 0:
            exit(1)

    logging.success("Configurations reload finished!")

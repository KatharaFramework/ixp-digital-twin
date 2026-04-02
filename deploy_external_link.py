import logging

from Kathara.manager.Kathara import Kathara
from Kathara.setting.Setting import Setting

from ixp.colored_logging import set_logging
from ixp.network_scenario.network_scenario_manager import NetworkScenarioManager
from ixp.settings.settings import Settings

if __name__ == "__main__":
    set_logging()

    settings = Settings.get_instance()
    settings.load_from_disk()

    Setting.get_instance().load_from_dict({"manager_type": "docker"})

    net_scenario_manager = NetworkScenarioManager()
    host_cd = net_scenario_manager.attach_host_interface()

    if host_cd is not None:
        Kathara.get_instance().deploy_link(host_cd)

    net_scenario_manager.on_deploy()

    logging.success("External link deployed successfully!")

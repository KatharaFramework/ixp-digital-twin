import logging
import re

from Kathara.model.Lab import Lab

from ..foundation.quarantine.action import Action
from ..foundation.quarantine.action_result import ActionResult
from ..model.bgp_neighbour import BGPNeighbour
from ..network_scenario.rs_manager import RouteServerManager
from ..settings.settings import Settings
from ..utils import class_for_name


class ActionManager:
    __slots__ = ['_actions', '_rs_manager']

    def __init__(self, exclude: list[str] | None = None):
        self._actions: dict[str, Action] = {}
        self._rs_manager: RouteServerManager = RouteServerManager()

        self._load_actions(exclude)

    def check(self, net_scenario: Lab, members: dict[str, BGPNeighbour], **kwargs) -> list[ActionResult]:
        if 'asn' not in kwargs:
            raise ValueError("No participant ASN specified.")
        if 'mac' not in kwargs:
            raise ValueError("No participant MAC address specified.")
        if 'ipv4' not in kwargs and 'ipv6' not in kwargs:
            raise ValueError("No participant IPv4 or IPv6 address specified.")

        results = []

        logging.info("Starting quarantine checks...")
        for action in self._actions.values():
            logging.info(f"Starting `{action.display_name()}` verification...")
            action_result = action.verify(net_scenario, members, self._rs_manager, **kwargs)
            results.append(action_result)

        return results

    def run_action_by_name(
            self, check_name: str, net_scenario: Lab, members: dict[str, BGPNeighbour], **kwargs
    ) -> ActionResult:
        if 'asn' not in kwargs:
            raise ValueError("No participant ASN specified.")
        if 'mac' not in kwargs:
            raise ValueError("No participant MAC address specified.")
        if 'ipv4' not in kwargs and 'ipv6' not in kwargs:
            raise ValueError("No participant IPv4 nor IPv6 address specified.")

        action = self._actions[check_name]
        logging.info(f"Starting `{action.display_name()}` verification...")
        action_result = action.verify(net_scenario, members, self._rs_manager, **kwargs)
        action.clean(net_scenario, members, self._rs_manager, **kwargs)

        return action_result

    def clean_action_by_name(
            self, check_name: str, net_scenario: Lab, members: dict[str, BGPNeighbour], **kwargs
    ) -> None:
        action = self._actions[check_name]
        logging.info(f"Cleaning `{action.display_name()}`...")
        action.clean(net_scenario, members, self._rs_manager, **kwargs)

    def _load_actions(self, exclude: list[str] | None = None):
        for action_name in Settings.get_instance().quarantine["actions"]:
            (subfolder, class_name) = action_name.split(".")
            class_name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()

            module_name = f"ixp.quarantine.{subfolder}"
            action_obj = class_for_name(module_name, class_name)()

            if exclude is None or action_obj.name() not in exclude:
                self._actions[action_name] = action_obj

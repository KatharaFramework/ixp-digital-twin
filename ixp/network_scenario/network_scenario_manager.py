import itertools
import logging
import time

from Kathara.manager.Kathara import Kathara
from Kathara.model.ExternalLink import ExternalLink
from Kathara.model.Lab import Lab
from Kathara.model.Link import Link
from Kathara.model.Machine import Machine

from ..foundation.dumps.table_dump.table_dump import TableDump
from ..foundation.exceptions import TableDumpError
from ..globals import EXTERNAL_FABRIC_CD_NAME, L2_FABRIC_CD_NAME, SWITCH_DEVICE_NAME, GATEWAY_DEVICE_NAME, \
    BACKBONE_CD_NAME
from ..model.bgp_neighbour import BGPRouter
from ..model.collision_domain import CollisionDomain
from ..settings.settings import Settings
from ..utils import chunk_list


class NetworkScenarioManager:
    __slots__ = ['_net_scenario']

    def __init__(self) -> None:
        self._net_scenario: Lab = Lab(Settings.get_instance().scenario_name)

    def build(self, table_dump: TableDump) -> Lab:
        if not table_dump.entries:
            raise TableDumpError("Cannot create network scenario, empty table dump.")

        logging.info("Creating Kathara network scenario...")
        for neighbour in table_dump.entries.values():
            for router in neighbour.routers.values():
                self._build_device(router)

        return self._net_scenario

    def get(self) -> Lab:
        logging.info("Fetching Kathara network scenario...")
        self._net_scenario = Kathara.get_instance().get_lab_from_api(lab_name=Settings.get_instance().scenario_name)

        for cd_name, cd in sorted(self._net_scenario.links.items(), key=lambda x: x[0]):
            pairs = itertools.combinations(cd.machines, 2)
            for d1, d2 in pairs:
                CollisionDomain.get_instance().update_assignment(d1, d2, cd_name)

        return self._net_scenario

    def build_diff(self, table_dump: TableDump) -> Lab:
        if not table_dump.entries:
            raise TableDumpError("Cannot create network scenario, empty table dump.")

        self._net_scenario = self.get()

        logging.info("Updating Kathara network scenario...")
        dump_entries = dict([
            (router.get_name(), router)
            for as_num, neighbour in table_dump.entries.items() for router in neighbour.routers.values()
        ])
        lab_entries = set([x for x in self._net_scenario.machines.keys() if 'as' in x])

        machines_to_add = set([x for x, _ in dump_entries.items()]) - lab_entries
        machines_to_del = lab_entries - set([x for x, _ in dump_entries.items()])

        for device_name in machines_to_add:
            router = dump_entries[device_name]
            # Machine not in the lab means either it was skipped before or it is a new peering to add
            if not self._net_scenario.has_machine(device_name):
                device = self._build_device(router)
                if device:
                    # Add a meta to notify that this is a new device
                    device.add_meta("new", True)

        for device_name in machines_to_del:
            if self._net_scenario.has_machine(device_name):
                device = self._net_scenario.get_machine(device_name)
                device.add_meta("del", True)

        return self._net_scenario

    def interconnect(self, table_dump: TableDump) -> None:
        arp_entries_cmd = self._generate_arp_entries(table_dump)

        switch_cds = set()
        for device in self._net_scenario.machines.values():
            for interface in device.interfaces.values():
                if interface.link.name == BACKBONE_CD_NAME:
                    continue

                switch_cds.add(interface.link.name)
                self._net_scenario.update_file_from_list(arp_entries_cmd, f"{device.name}.startup")

        host_cd = self._attach_host_interface()
        if host_cd is not None:
            switch_cds.add(host_cd.name)

        switch = self._net_scenario.new_machine(SWITCH_DEVICE_NAME)
        switch.add_meta("sysctl", "net.ipv4.conf.all.proxy_arp=1")
        switch_startup_cmds = ["ip link add br1 type bridge", "brctl setageing br1 9999999999999"]
        for cd in switch_cds:
            iface_num = self._net_scenario.connect_machine_obj_to_link(switch, cd).num
            switch_startup_cmds.append(f"ip link set eth{iface_num} master br1")
        switch_startup_cmds.append("ip link set dev br1 up")
        self._net_scenario.create_file_from_list(switch_startup_cmds, "switch.startup")

    def update_interconnection(
            self, table_dump: TableDump, new_devices: dict[str, Machine], del_devices: set[str]
    ) -> None:
        logging.info("Updating network interconnections...")

        arp_entries_cmd = "/bin/bash -c '" + "; ".join(self._generate_arp_entries(table_dump, del_devices)) + "'"

        switch_cds = set()
        for device in new_devices.values():
            for interface in device.interfaces.values():
                switch_cds.add(interface.link)

        # Update arp entries in all the devices
        for device in self._net_scenario.machines.values():
            if device.name in [SWITCH_DEVICE_NAME, GATEWAY_DEVICE_NAME]:
                continue

            Kathara.get_instance().exec_obj(machine=device, command="ip neigh flush all dev eth0", stream=False)
            Kathara.get_instance().exec_obj(machine=device, command=arp_entries_cmd, stream=False)

        switch = self._net_scenario.get_machine(SWITCH_DEVICE_NAME)
        switch_cmds = []
        for cd in switch_cds:
            Kathara.get_instance().connect_machine_to_link(switch, cd)
            iface_num = list(switch.interfaces.values())[-1].num
            switch_cmds.append(f"ip link set eth{iface_num} master br1")

        Kathara.get_instance().exec_obj(
            machine=switch, command="/bin/bash -c '" + "; ".join(switch_cmds) + "'", stream=False
        )

        logging.success("Network interconnections updated!")

    def _build_device(self, router: BGPRouter) -> Machine | None:
        device_name = router.get_name()

        if not router.routes[4] and not router.routes[6]:
            logging.info(f"Skipping device `{device_name}` because it has no routes")
            return None

        mac_address = set(peering.l2_address for v_peerings in router.peerings.values() for peering in v_peerings)
        mac_address = set(filter(lambda x: x is not None, mac_address))
        if len(mac_address) > 1:
            logging.error(f"Cannot create device `{device_name}` as more than one MAC address is specified.")
            return None

        device = self._net_scenario.new_machine(device_name)
        device.add_meta("ipv6", len(router.peerings[6]) > 0)

        # Create a collision domain between the device and the switch
        cd = CollisionDomain.get_instance().get(device.name, L2_FABRIC_CD_NAME)
        self._net_scenario.connect_machine_obj_to_link(
            device, cd, mac_address=mac_address.pop() if mac_address else None
        )

        for v, peerings in router.peerings.items():
            peering_lan = Settings.get_instance().peering_lan[f"{v}"]
            self._net_scenario.update_file_from_list(
                [f"ip addr add {peering.l3_address}/{peering_lan.prefixlen} dev eth0" for peering in peerings],
                f"{device_name}.startup",
            )

        logging.success(f"Device `{device_name}` created.")

        return device

    def _attach_host_interface(self) -> Link | None:
        host_iface = Settings.get_instance().host_interface

        if host_iface is None:
            logging.warning("No host interface specified! It is not possible to connect external peers!")
            return None

        peering_cd = self._net_scenario.get_or_new_link(EXTERNAL_FABRIC_CD_NAME)

        vlan = None
        if "." in host_iface:
            iface_name, vlan = host_iface.split(".")
            vlan = int(vlan)
        else:
            iface_name = host_iface
        peering_cd.external.append(ExternalLink(iface_name, vlan))

        logging.success(f"Attached collision domain `{EXTERNAL_FABRIC_CD_NAME}` to host interface `{host_iface}`.")

        return peering_cd

    def deploy_chunks(self) -> None:
        logging.info("Deploying network scenario...")

        machines = set(self._net_scenario.machines.keys())
        main_chunk = set(filter(lambda x: "rs" in x, machines))
        main_chunk.add(SWITCH_DEVICE_NAME)

        Kathara.get_instance().deploy_lab(self._net_scenario, selected_machines=main_chunk)
        deployed_machines = len(main_chunk)
        logging.info(f"Deployed devices: {deployed_machines}/{len(machines)}")

        for chunk in chunk_list(list(machines - main_chunk), 5):
            Kathara.get_instance().deploy_lab(self._net_scenario, selected_machines=set(chunk))
            deployed_machines += len(chunk)
            logging.info(f"Deployed devices: {deployed_machines}/{len(machines)}")

        self.on_deploy()

        logging.success("Network scenario deployed!")

    @staticmethod
    def deploy_devices(devices: dict[str, Machine]) -> None:
        logging.info("Deploying new devices...")

        for name, device in devices.items():
            Kathara.get_instance().deploy_machine(device)

        # Wait for machines to be running
        all_started = False
        while not all_started:
            time.sleep(2)
            for device in devices.values():
                device.api_object.reload()
                if device.api_object.status != "running":
                    break
            all_started = True

        logging.success("New devices deployed!")

    @staticmethod
    def undeploy_devices(devices: dict[str, Machine]) -> None:
        logging.info("Undeploying removed devices...")

        for name, device in devices.items():
            Kathara.get_instance().undeploy_machine(device)

        logging.success("Devices undeployed!")

    @staticmethod
    def on_deploy() -> None:
        host_iface = Settings.get_instance().host_interface

        if host_iface is None:
            return

        logging.info(f"Setting interface {host_iface} to promiscuous mode...")

        from pyroute2 import IPRoute
        ip = IPRoute()

        interface_indexes = ip.link_lookup(ifname=host_iface)
        ip.link(
            "set",
            index=interface_indexes[0],
            promiscuity=1,
            state="up"
        )

        ip.close()

        logging.info(f"Interface {host_iface} set to promiscuous mode.")

    @staticmethod
    def copy_and_exec_by_device_info(device_info: dict) -> int:
        for device, (paths, cmd, has_errors) in device_info.items():
            logging.info(f"Copying {paths} into device `{device.name}`...")

            Kathara.get_instance().copy_files(device, paths)
            for guest_path in paths:
                if ".tar.gz" in guest_path:
                    tar_cmd = f"/bin/bash -c \"tar -xvf {guest_path} -C {guest_path.split('.')[0]}; rm -r {guest_path}\""
                    logging.info(f"Executing command `{tar_cmd}` in device `{device.name}`...")
                    _, stderr, exit_code = Kathara.get_instance().exec_obj(device, tar_cmd, stream=False)
                    if exit_code != 0:
                        raise Exception(stderr)

            logging.info(f"Executing command `{cmd}` in device `{device.name}`...")
            stdout, stderr, exit_code = Kathara.get_instance().exec_obj(device, cmd, stream=False)
            stdout = stdout.decode("utf-8") if stdout else None
            stderr = stderr.decode("utf-8") if stderr else None
            if exit_code != 0:
                logging.warning(f"Error while updating configuration in device `{device.name}`:\n{stderr}")
                return 1
            else:
                if not has_errors(stdout, stderr):
                    logging.info(f"`{cmd}` in device `{device.name}` returned output:\n{stdout}")
                else:
                    logging.warning(f"Error while updating configuration in device `{device.name}`:\n{stdout}")
                    return 1

        return 0

    def undeploy(self, except_machines: set = None) -> None:
        if except_machines is None:
            except_machines = set()

        logging.info("Undeploying network scenario...")
        Kathara.get_instance().undeploy_lab(
            lab=self._net_scenario,
            selected_machines=set(self._net_scenario.machines.keys()) - except_machines,
        )
        logging.success("Network scenario undeployed!")

    @staticmethod
    def _generate_arp_entries(table_dump: TableDump, exclude: set[str] | None = None) -> list[str]:
        if exclude is None:
            exclude = set()

        return [
            f"ip neigh add {peering.l3_address} lladdr {peering.l2_address} dev eth0"
            for neighbor in table_dump.entries.values()
            for router in neighbor.routers.values()
            if (router.routes[4] or router.routes[6]) and (router.get_name() not in exclude)
            for v_peering in router.peerings.values()
            for peering in v_peering
        ]

import json

from ...foundation.dumps.member_dump.member_dump import MemberDump
from ...model.bgp_neighbour import BGPNeighbour


class IxpManagerDump(MemberDump):
    def load_from_file(self, path: str) -> dict[str, BGPNeighbour]:
        entries = {}

        with open(path, "r") as config_file:
            config = json.load(config_file)

        for member in config["member_list"]:
            routers = enumerate(filter(lambda x: x["vlan_list"], member["connection_list"]))
            as_num = member["asnum"]
            for idx, router in routers:
                member_name = f"as{as_num}"
                if member_name not in entries:
                    entries[member_name] = BGPNeighbour(member["asnum"])

                if idx not in entries[member_name].routers:
                    entries[member_name].add_router(idx)

                as_router = entries[member_name].routers[idx]

                for vlan_list in router["vlan_list"]:
                    for v in [4, 6]:
                        ipv_str = f"ipv{v}"
                        if ipv_str in vlan_list:
                            v_vlan = vlan_list[ipv_str]
                            mac_addr = v_vlan["mac_addresses"].pop() if v_vlan["mac_addresses"] else None
                            if mac_addr is None:
                                if as_num not in self._as_to_generated_mac:
                                    self._as_to_generated_mac[as_num] = self._generate_mac_address()
                                mac_addr = self._as_to_generated_mac[as_num]
                            as_router.add_peering(mac_addr, v_vlan["address"])

        return entries

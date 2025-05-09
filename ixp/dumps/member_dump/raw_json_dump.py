import json

from ...foundation.dumps.member_dump.member_dump import MemberDump
from ...model.bgp_neighbour import BGPNeighbour


class RawJsonDump(MemberDump):
    def load_from_file(self, path: str) -> dict[str, BGPNeighbour]:
        entries = {}

        with open(path, "r") as config_file:
            config = json.load(config_file)

        for member in config:
            member_name = f"as{member['ORIG_AS_NUM']}"
            if member_name not in entries:
                entries[member_name] = BGPNeighbour(member['ORIG_AS_NUM'])
            router = entries[member_name].add_router(len(entries[member_name].routers))

            if member['MAC_ADDR']:
                mac_addr = member['MAC_ADDR'].replace('.', '')
                mac_addr = ':'.join(mac_addr[i:i + 2] for i in range(0, len(mac_addr), 2))
            else:
                mac_addr = self._generate_mac_address()

            if member['PEERING_ADDR4']:
                router.add_peering(mac_addr, member['PEERING_ADDR4'])
            if member['PEERING_ADDR6']:
                router.add_peering(mac_addr, member['PEERING_ADDR6'])

        return entries

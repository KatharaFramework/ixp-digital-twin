import ipaddress
import logging
import os
import re

from ...foundation.dumps.table_dump.table_dump import TableDump


class OpenBgpdTableDump(TableDump):
    def load_from_file(self, path: str) -> None:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Table dump in path `{path}` not found.")

        logging.info(f"Loading Dump in `{path}`...")
        with open(path, "r") as f:
            lines = f.readlines()

        # If the dump contains header rows, skip them
        if "flags" in lines[0]:
            lines = lines[6:]

        for line in lines:
            if not line:
                continue

            (_, rpki, network, neighbor_ip, _, _, path) = re.split(r"\s+", line, maxsplit=6)
            if rpki == "!":
                continue

            path_list = list(filter(lambda x: x not in ["i", "e", "?", ""], re.split(r"\s+", path)))
            neighbor_as = path_list[0] if path_list else None

            if not neighbor_as:
                logging.warning(f"AS Path for network {network} is empty, skipping...")
                continue

            neighbor_name = f"as{neighbor_as}"
            neighbor_ip_address = ipaddress.ip_address(neighbor_ip)

            for router in self.entries[neighbor_name].routers.values():
                if router.has_peering(neighbor_ip_address):
                    router.add_route(network, path_list)

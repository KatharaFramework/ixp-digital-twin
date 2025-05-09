import ast
import ipaddress
import logging
import os
import re

from ...foundation.dumps.table_dump.table_dump import TableDump


class BirdTableDump(TableDump):
    def load_from_file(self, path: str) -> None:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Table dump in path `{path}` not found.")

        logging.info(f"Loading Dump in `{path}`...")
        with open(path, "r") as f:
            lines = f.readlines()

        routes = []
        current_route = {}

        for line in lines[2:]:
            line = line.strip()

            match = re.match(rf"Table T_roa_", line)
            if match:
                break

            match = re.match(rf'^(.+)\s+\w+\s+\[(\w+) (.*?)\]', line)
            if match:
                network, neighbor_name, timestamp = match.groups()
                current_route = {
                    'network': ipaddress.ip_network(network.strip()),
                    'neighbor_name': neighbor_name,
                    'timestamp': timestamp,
                    'attributes': {}
                }
                routes.append(current_route)

            # Match next hop
            match = re.match(rf'^via (.+) on (\w+)', line)
            if match:
                current_route['neighbor_ip_address'] = ipaddress.ip_address(match.group(1))
                current_route['interface'] = match.group(2)
                continue

            # Match BGP attributes
            match = re.match(r'^BGP\.(\w+): (.+)', line)
            if match:
                attr, value = match.groups()
                if attr == 'next_hop':
                    current_route['attributes'][attr] = [ipaddress.ip_address(value) for value in value.split(' ')]
                elif attr == 'as_path':
                    current_route['attributes'][attr] = []
                    for value in value.split(' '):
                        value = ast.literal_eval(value)
                        if isinstance(value, set):
                            current_route['attributes'][attr].append(value.pop())
                        else:
                            current_route['attributes'][attr].append(value)
                    current_route['as'] = current_route["attributes"][attr][0]
                else:
                    current_route['attributes'][attr] = value
                continue

        for route in routes:
            for router in self.entries[f'as{route["as"]}'].routers.values():
                if router.has_peering(route['neighbor_ip_address']):
                    router.add_route(str(route['network']), route['attributes']['as_path'])

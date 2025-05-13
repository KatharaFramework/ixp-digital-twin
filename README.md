# IXP Digital Twin

A tool for generating an emulation-based digital twin for Internet Exchange Points (IXPs), starting from production
configurations. It allows IXPs to test and validate route server configurations in a controlled environment.

## Overview

The tool analyzes configuration files and generates a Kathará network scenario, where the route-servers of the emulated
IXP expose the same information of the real-world ones.

Route servers Docker images are based on the same version of the software used in the production environment.
Peers are emulated as FRRouting routers and inject the same routes, with the same origin AS and AS-path, as the real
peers.

The tool also offers a set of quarantine checks to validate that customer configurations are compliant with the
requirements of the IXP. Thanks to the Kathará external feature, it is possible to attach real devices to the emulated
network, so in the onboarding process customers can validate their configurations in the emulated environment before
being attached to the production network.

## Why Use IXP Digital Twin?

- **Test Environment**: Run tests on configurations before applying them in production, ensuring stability and reducing
  downtime.
- **Failure Simulation**: Emulate network failures and validate your mitigations before implementing in the real world.
- **Training Grounds**: Train staff on your network setup using a risk-free replica environment.
- **Simplified Onboarding**: Help new customers validate their configurations safely before connection.

Need assistance configuring for your specific IXP? Contact our support team at `contact@kathara.org`.

### Quarantine Checks

The quarantine checks are a suite of automated actions designed to validate customer configurations and ensure they meet
the requirements of the IXP before being integrated into the production environment. These checks address multiple
aspects of network stability, security, and compliance:

1. **Connectivity Validation**
    - **Ping Tests**: Verifies connectivity using ICMP to ensure reachability between devices.
    - **MTU Verification**: Confirms that the Maximum Transmission Unit (MTU) settings are correctly configured to
      prevent packet fragmentation.
    - **Proxy ARP Checks**: Ensures proxy ARP is functioning properly, verifying that devices can respond to ARP
      requests on behalf of others if needed.

2. **BGP Routing Checks**
    - **Session Validation**: Confirms that BGP sessions are correctly established between peers and comply with
      protocol requirements.
    - **Routing Information Base (RIB) Verification**: Ensures that the number of advertised prefixes does not exceed
      predefined limits for IPv4 and IPv6.

3. **Security Audits**
    - **Active Services Monitoring**: Identifies and validates running services to ensure there are no unauthorized
      processes.
    - **Traffic Pattern Analysis**: Dumps and inspects network traffic over a configurable time period to detect
      anomalies or policy violations.

These quarantine checks ensure that all configurations are stable, secure, and fully compliant with IXP policies before
allowing new devices or customers to connect to the production network. This greatly reduces the risk of operational
disruptions and enhances the reliability of the IXP environment.

If you are interested in the quarantine checks, we also offer a GUI to allow customers to run the checks directly from a
browser. The GUI shows information about the current status of the checks providing suggestions on how to fix the
configuration in case of failures.

For more details refer to: https://github.com/KatharaFramework/ixp-quarantine-dashboard

## Prerequisites

- Python 3.11 or higher
- Docker (for running route server containers)
- Network interface for external LAN connectivity

## Getting Started

1. **Configure the environment**:
    - Copy `ixp.conf.example` to `ixp.conf`
    - Edit the configuration file with your specific IXP settings:
        - Scenario name
        - Network interface
        - Peering LAN subnets (IPv4/IPv6)
        - Route server settings
        - RPKI configuration
        - Quarantine parameters

2. **Prepare required resources**:
    - Place configuration files in the `resources` folder:
        - Peering configuration JSON
        - RIB dumps (.dump files)
        - Route server configs

3. **Install dependencies**:
   ```bash
   python3 -m pip install -r requirements.txt
   ```

4. **Launch the Digital Twin**:
   ```bash
   python3 start.py
   ```

## Managing Route Servers

### Updating Configurations

1. Modify the configuration files in the `resources` directory
2. Apply changes by running:
   ```bash
   python3 reload.py
   ```

## Running the Quarantine Checks

To run the quarantine checks, use the following command syntax:

```shell script
python3 check.py --asn <ASN> --mac <MAC-ADDRESS> [--ipv4 <IPv4-ADDRESS>] [--ipv6 <IPv6-ADDRESS>] [--exclude_checks <CHECKS>] [--result-level <LEVEL>]
```

| Parameter          | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| `--asn`            | The Autonomous System Number (ASN) for the peer being checked.              |
| `--mac`            | The MAC address of the peer device.                                         |
| `--ipv4`           | The IPv4 address of the peer device (optional).                             |
| `--ipv6`           | The IPv6 address of the peer device (optional).                             |
| `--exclude_checks` | A comma-separated list of checks to exclude (e.g., `ping,mtu,bgp-session`). |

The script outputs detailed logs about the validation process, including which checks were performed and their results.
You can configure verbosity using the `--result-level` parameter.

## Configuration Structure

The `ixp.conf` file contains the following main sections:

- **scenario_name**: Identifies your IXP deployment
- **host_interface**: Network interface for external connections
- **peering_lan**: IPv4/IPv6 subnets for the peering LAN
- **peering_configuration**: JSON-based configuration settings
- **rib_dumps**: Route Information Base table dumps
- **route_servers**: Configuration for BGP route servers
- **rpki**: RPKI validation server settings
- **quarantine**: Security and connectivity validation checks

## Support Us

The ixp-digital-twin project is an open source project funded and created in collaboration
with [Namex](https://www.namex.it/),
the IXP of Rome.

Currently, also [VSIX](https://www.vs-ix.org) funds and collaborates on the project.

If you want to collaborate on the project or on new ideas, please contact us at `contact@kathara.org`.

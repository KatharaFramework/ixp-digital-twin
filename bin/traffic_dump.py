import argparse
import ipaddress
import json
import logging

from scapy.all import sniff
from scapy.arch import get_if_hwaddr
from scapy.layers.inet import IP, ICMP, TCP
from scapy.layers.inet6 import IPv6, ICMPv6ND_NA, ICMPv6ND_NS, ICMPv6EchoRequest, ICMPv6EchoReply
from scapy.layers.l2 import Ether, ARP, STP
from scapy.packet import Packet
from scapy.sessions import IPSession

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)


def get_packet_layers(packet):
    counter = 0
    while True:
        layer = packet.getlayer(counter)
        if layer is None:
            break

        yield layer
        counter += 1


def is_unauthorized_pkt(
        pkt: Packet, macs_whitelist: set, mac: str, ip: ipaddress.IPv4Address | ipaddress.IPv6Address, version: int,
) -> bool:
    # Is STP packet
    if STP in pkt:
        return True

    # Involves the participant's MAC (source or destination)
    if pkt[Ether].dst != mac and pkt[Ether].src != mac:
        return False

    is_participant_dst = pkt[Ether].dst == mac
    other_mac = pkt[Ether].src if is_participant_dst else pkt[Ether].dst
    # Does not involve other IXP MACs
    if other_mac in macs_whitelist:
        return False

    # Is not of type ARP and broadcast (for IPv4) || is not ICMPv6 NA or NS (for IPv6)
    if version == 4 and (ARP in pkt and pkt[Ether].dst == "ff:ff:ff:ff:ff:ff"):
        return False
    if version == 6 and (ICMPv6ND_NA in pkt or ICMPv6ND_NS in pkt):
        return False

    if IP in pkt and version == 4:
        src_ip = ipaddress.ip_address(pkt[IP].src)
    elif IPv6 in pkt and version == 6:
        src_ip =  ipaddress.ip_address(pkt[IPv6].src)
    else:
        return False
    # Is not originated by the participant's IP && has source or destination port as 179/tcp, and
    if (IP in pkt or IPv6 in pkt) and src_ip == ip:
        if TCP in pkt and (pkt[TCP].sport == 179 or pkt[TCP].dport == 179):
            return False

    # Is not originated by the participant's IP && (is ICMP echo request || ICMP echo reply) || (ICMPv6 for IPv6)
    if version == 4 and IP in pkt and src_ip == ip:
        if ICMP in pkt and (pkt[ICMP].type in [8, 0]):  # Echo request or reply
            return False
    if version == 6 and IPv6 in pkt and src_ip == ip:
        if ICMPv6EchoRequest in pkt or ICMPv6EchoReply in pkt:
            return False

    return True


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('iface', nargs=1, type=str)
    parser.add_argument('sniff_time', nargs=1, type=int)
    parser.add_argument('mac_whitelist', nargs=1, type=str)
    parser.add_argument('mac', nargs=1, type=str)
    parser.add_argument('ip', nargs=1, type=str)
    parser.add_argument('version', nargs=1, type=int)

    return parser.parse_args()


def main(args):
    iface = args.iface.pop()
    sniff_time = args.sniff_time.pop()
    macs_whitelist = set(args.mac_whitelist.pop().split(','))
    mac = args.mac.pop()
    ip = ipaddress.ip_address(args.ip.pop())
    version = args.version.pop()

    # Add own MAC address to the whitelist
    local_iface_mac = get_if_hwaddr(iface)
    macs_whitelist.add(local_iface_mac)

    unauthorized_pkts: list[Packet] = []

    def packet_callback(pkt):
        if is_unauthorized_pkt(pkt, macs_whitelist, mac, ip, version):
            unauthorized_pkts.append(pkt)

    sniff(
        iface=iface,
        session=IPSession,
        prn=packet_callback,
        store=False,
        timeout=sniff_time
    )

    print(json.dumps([" / ".join([layer.mysummary() for layer in get_packet_layers(x)]) for x in unauthorized_pkts]))
    exit(0)


if __name__ == "__main__":
    main(parse_args())

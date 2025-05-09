import re

PING_LOSS_REGEX = re.compile(r"(\d+)% packet loss")

OPENBGPD_SESSION_REMOTE_AS = re.compile(r"remote AS (\d+)")
OPENBGPD_SESSION_UPTIME = re.compile(r"up for ([\d:]+)")
OPENBGPD_RIB_PREFIX = re.compile(r"BGP routing table entry for (\S+)")
OPENBGPD_RIB_NEXTHOP = re.compile(r"Nexthop (\S+)")

BIRD_SESSION_REMOTE_AS = re.compile(r"Neighbor AS: +(\d+)")
BIRD_SESSION_UPTIME = re.compile(r"up +([\d:\- ]+) +Established")
BIRD_RIB_PREFIX = re.compile(r"(\S+) +via")
BIRD_RIB_NEXTHOP = re.compile(r"BGP.next_hop: +(\S+)")
BIRD_RIB_AS_PATH = re.compile(r"BGP.as_path: +(.+?)\n")

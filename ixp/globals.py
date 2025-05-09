import os
from pathlib import Path

PATH_PREFIX = os.path.relpath(Path(os.path.dirname(__file__)).parent)
RESOURCES_FOLDER: str = os.path.abspath(os.path.join(PATH_PREFIX, "resources"))
BIN_FOLDER: str = os.path.abspath(os.path.join(PATH_PREFIX, "./bin"))
SWITCH_DEVICE_NAME: str = "switch"
L2_FABRIC_CD_NAME: str = "l2_fabric"
EXTERNAL_FABRIC_CD_NAME: str = "ext_fabric"
GATEWAY_DEVICE_NAME: str = "ixp_gateway"
BACKBONE_CD_NAME: str = "backbone"
BACKBONE_IP_PREFIX: str = "10.0.0.0/24"

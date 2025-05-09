import importlib
import subprocess
import sys
from typing import Generator, Any

from Kathara.model.Machine import Machine
from Kathara.setting.Setting import Setting

from .globals import PATH_PREFIX


def class_for_name(module_name: str, class_name: str) -> Any:
    m = importlib.import_module(
        f"{module_name}.{class_name}" if PATH_PREFIX == "." else f"{PATH_PREFIX}.{module_name}.{class_name}")
    camel_case_class_name = "".join(map(lambda x: x.capitalize(), class_name.split("_")))
    return getattr(m, camel_case_class_name)


def chunk_list(input_list: list, size: int) -> Generator[list, None, None]:
    for i in range(0, len(input_list), size):
        yield input_list[i: i + size]


def open_terminal(device: Machine) -> None:
    command = (
            '%s -c "from Kathara.manager.Kathara import Kathara; '
            "Kathara.get_instance().connect_tty('%s', lab_name='%s', shell='%s', logs=True)\""
            % (sys.executable, device.name, device.lab.name, Setting.get_instance().device_shell)
    )
    subprocess.Popen([Setting.get_instance().terminal, "-e", command], start_new_session=True)


def is_device_ipv6(device: Machine) -> bool:
    if "net.ipv6.conf.all.forwarding" in device.meta["sysctls"]:
        return device.meta["sysctls"]["net.ipv6.conf.all.forwarding"] == "1"

    return False

import subprocess
from typing import List, Optional

import pkg_resources

from dstack._internal.backend.base.compute import Compute
from dstack._internal.backend.base.head import (
    delete_head_object,
    list_head_objects,
    put_head_object,
)
from dstack._internal.backend.base.storage import Storage
from dstack._internal.core.error import DstackError
from dstack._internal.core.gateway import GatewayHead
from dstack._internal.hub.utils.ssh import HUB_PRIVATE_KEY_PATH
from dstack._internal.utils.common import PathLike
from dstack._internal.utils.random_names import generate_name


def create_gateway(compute: Compute, storage: Storage, ssh_key_pub: str) -> GatewayHead:
    # todo generate while instance name is not unique
    instance_name = f"dstack-gateway-{generate_name()}"
    head = compute.create_gateway(instance_name, ssh_key_pub)
    put_head_object(storage, head)
    return head


def list_gateways(storage: Storage) -> List[GatewayHead]:
    return list_head_objects(storage, GatewayHead)


def delete_gateway(compute: Compute, storage: Storage, instance_name: str):
    heads = list_gateways(storage)
    for head in heads:
        if head.instance_name != instance_name:
            continue
        compute.delete_instance(instance_name)
        delete_head_object(storage, head)


def publish(
    hostname: str,
    port: int,
    ssh_key: bytes,
    user: str = "ubuntu",
    id_rsa: Optional[PathLike] = HUB_PRIVATE_KEY_PATH,
) -> str:
    command = ["sudo", "python3", "-", hostname, str(port), f'"{ssh_key.decode().strip()}"']
    with open(
        pkg_resources.resource_filename("dstack._internal", "scripts/gateway_publish.py"), "r"
    ) as f:
        output = exec_ssh_command(
            hostname, command=" ".join(command), user=user, id_rsa=id_rsa, stdin=f
        )
    return output.decode().strip()


def exec_ssh_command(
    hostname: str, command: str, user: str, id_rsa: Optional[PathLike], stdin=None
) -> bytes:
    args = ["ssh"]
    if id_rsa is not None:
        args += ["-i", id_rsa]
    args += [
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{user}@{hostname}",
        command,
    ]
    proc = subprocess.Popen(args, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise SSHCommandError(args, stderr.decode())
    return stdout


class SSHCommandError(DstackError):
    def __init__(self, cmd: List[str], message: str):
        super().__init__(message)
        self.cmd = cmd

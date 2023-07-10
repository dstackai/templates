from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Extra, Field, validator
from typing_extensions import Annotated, Literal


class PythonVersion(str, Enum):
    PY37 = "3.7"
    PY38 = "3.8"
    PY39 = "3.9"
    PY310 = "3.10"
    PY311 = "3.11"


class ForbidExtra(BaseModel):
    class Config:
        extra = Extra.forbid


class RegistryAuth(ForbidExtra):
    username: Optional[str]
    password: str


class Artifact(ForbidExtra):
    path: str
    mount: bool = False


class BaseConfiguration(ForbidExtra):
    type: Literal["none"]
    image: Optional[str]
    entrypoint: Optional[str]
    home_dir: str = "/root"
    registry_auth: Optional[RegistryAuth]
    python: Optional[PythonVersion]
    ports: List[Union[str, int]] = []
    env: Dict[str, str] = {}
    build: List[str] = []
    cache: List[str] = []

    @validator("python", pre=True, always=True)
    def convert_python(cls, v, values) -> Optional[PythonVersion]:
        if v is not None and values.get("image"):
            raise KeyError("`image` and `python` are mutually exclusive fields")
        if isinstance(v, float):
            v = str(v)
            if v == "3.1":
                v = "3.10"
        if isinstance(v, str):
            return PythonVersion(v)
        return v


class DevEnvironmentConfiguration(BaseConfiguration):
    type: Literal["dev-environment"] = "dev-environment"
    ide: Literal["vscode"]
    init: List[str] = []


class TaskConfiguration(BaseConfiguration):
    type: Literal["task"] = "task"
    commands: List[str]
    artifacts: List[Artifact] = []


class DstackConfiguration(BaseModel):
    __root__: Annotated[
        Union[DevEnvironmentConfiguration, TaskConfiguration], Field(discriminator="type")
    ]


def parse(data: dict) -> Union[DevEnvironmentConfiguration, TaskConfiguration]:
    return DstackConfiguration.parse_obj(data).__root__

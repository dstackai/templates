from dataclasses import dataclass
from typing import List, Optional

from pydantic import BaseModel

from dstack._internal.core.runners import Resources


class InstanceType(BaseModel):
    instance_name: str
    resources: Resources
    available_regions: Optional[List[str]] = None


class LaunchedInstanceInfo(BaseModel):
    request_id: str
    location: Optional[str] = None


@dataclass(frozen=True)
class InstanceOffer:
    instance_type: InstanceType
    region: str
    spot: bool
    price: float

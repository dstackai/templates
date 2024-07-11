from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import Field, root_validator, validator
from typing_extensions import Annotated, Literal

from dstack._internal.core.models.backends.base import BackendType
from dstack._internal.core.models.common import CoreModel
from dstack._internal.core.models.pools import Instance
from dstack._internal.core.models.profiles import (
    DEFAULT_POOL_TERMINATION_IDLE_TIME,
    Profile,
    ProfileParams,
    ProfileRetry,
    SpotPolicy,
    TerminationPolicy,
    parse_duration,
)
from dstack._internal.core.models.resources import Range, ResourcesSpec


class FleetStatus(str, Enum):
    # Currently all fleets are active
    # submitted/failed may be used if fleets require async processing
    SUBMITTED = "submitted"
    ACTIVE = "active"
    FAILED = "failed"


class InstanceGroupPlacement(str, Enum):
    ANY = "any"
    CLUSTER = "cluster"


class InstanceGroupParams(CoreModel):
    nodes: Annotated[Range[int], Field(description="The number of instances")]
    placement: Annotated[
        Optional[InstanceGroupPlacement],
        Field(description="The placement of instances"),
    ] = None
    resources: Annotated[
        Optional[ResourcesSpec],
        Field(description="The resources requirements"),
    ] = ResourcesSpec()

    backends: Annotated[
        Optional[List[BackendType]],
        Field(description="The backends to consider for provisioning (e.g., `[aws, gcp]`)"),
    ] = None
    regions: Annotated[
        Optional[List[str]],
        Field(
            description="The regions to consider for provisioning (e.g., `[eu-west-1, us-west4, westeurope]`)"
        ),
    ] = None
    instance_types: Annotated[
        Optional[List[str]],
        Field(
            description="The cloud-specific instance types to consider for provisioning (e.g., `[p3.8xlarge, n1-standard-4]`)"
        ),
    ] = None
    spot_policy: Annotated[
        Optional[SpotPolicy],
        Field(
            description="The policy for provisioning spot or on-demand instances: `spot`, `on-demand`, or `auto`"
        ),
    ] = None
    retry: Annotated[
        Optional[Union[ProfileRetry, bool]],
        Field(description="The policy for provisioning retry. Defaults to `false`"),
    ] = None
    max_price: Annotated[
        Optional[float], Field(description="The maximum price per hour, in dollars", gt=0.0)
    ] = None
    termination_policy: Annotated[
        Optional[TerminationPolicy],
        Field(description="The policy for instance termination. Defaults to `destroy-after-idle`"),
    ] = None
    termination_idle_time: Annotated[
        Optional[Union[str, int]],
        Field(description="Time to wait before destroying idle instances. Defaults to `3d`"),
    ] = None

    _validate_termination_idle_time = validator(
        "termination_idle_time", pre=True, allow_reuse=True
    )(parse_duration)


class FleetProps(CoreModel):
    type: Literal["fleet"] = "fleet"
    name: Annotated[Optional[str], Field(description="The fleet name")] = None


class FleetConfiguration(FleetProps, InstanceGroupParams):
    pass


class FleetSpec(CoreModel):
    configuration: FleetConfiguration
    profile: Profile
    # TODO: make merged_profile a computed field after migrating to pydanticV2
    merged_profile: Annotated[Profile, Field(exclude=True)] = None

    class Config:
        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type) -> None:
            prop = schema.get("properties", {})
            prop.pop("merged_profile", None)

    @root_validator
    def _merged_profile(cls, values) -> Dict:
        try:
            merged_profile = Profile.parse_obj(values["profile"])
            conf = FleetConfiguration.parse_obj(values["configuration"])
        except KeyError:
            raise ValueError("Missing profile or configuration")
        for key in ProfileParams.__fields__:
            conf_val = getattr(conf, key, None)
            if conf_val is not None:
                setattr(merged_profile, key, conf_val)
        if merged_profile.spot_policy is None:
            merged_profile.spot_policy = SpotPolicy.AUTO
        if merged_profile.retry is None:
            merged_profile.retry = False
        if merged_profile.termination_policy is None:
            merged_profile.termination_policy = TerminationPolicy.DESTROY_AFTER_IDLE
        if merged_profile.termination_idle_time is None:
            merged_profile.termination_idle_time = DEFAULT_POOL_TERMINATION_IDLE_TIME
        values["merged_profile"] = merged_profile
        return values


class Fleet(CoreModel):
    name: str
    project_name: str
    spec: FleetSpec
    created_at: datetime
    status: FleetStatus
    status_message: Optional[str] = None
    instances: List[Instance]

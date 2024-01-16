import asyncio
import itertools
import math
import uuid
from datetime import timezone
from typing import List, Optional, Tuple

import pydantic
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

import dstack._internal.server.services.gateways as gateways
import dstack._internal.utils.common as common_utils
from dstack._internal.core.backends.base import Backend
from dstack._internal.core.backends.base.compute import (
    DockerConfig,
    InstanceConfiguration,
    SSHKeys,
)
from dstack._internal.core.errors import BackendError, RepoDoesNotExistError, ServerClientError
from dstack._internal.core.models.instances import (
    InstanceOfferWithAvailability,
    LaunchedInstanceInfo,
)
from dstack._internal.core.models.profiles import DEFAULT_POOL_NAME, Profile, SpotPolicy
from dstack._internal.core.models.runs import (
    GpusRequirements,
    Job,
    JobPlan,
    JobProvisioningData,
    JobSpec,
    JobStatus,
    JobSubmission,
    Requirements,
    Run,
    RunPlan,
    RunSpec,
    ServiceInfo,
    ServiceModelInfo,
)
from dstack._internal.core.models.users import GlobalRole
from dstack._internal.server.models import JobModel, PoolModel, ProjectModel, RunModel, UserModel
from dstack._internal.server.services import backends as backends_services
from dstack._internal.server.services import repos as repos_services
from dstack._internal.server.services.docker import parse_image_name
from dstack._internal.server.services.jobs import (
    get_jobs_from_run_spec,
    job_model_to_job_submission,
    stop_job,
)
from dstack._internal.server.services.jobs.configurators.base import (
    get_default_image,
    get_default_python_verison,
)
from dstack._internal.server.services.pools import create_pool_model, list_project_pool, show_pool
from dstack._internal.server.services.projects import list_project_models, list_user_project_models
from dstack._internal.server.utils.common import run_async
from dstack._internal.utils.logging import get_logger
from dstack._internal.utils.random_names import generate_name

logger = get_logger(__name__)


async def list_user_runs(
    session: AsyncSession,
    user: UserModel,
    project_name: Optional[str],
    repo_id: Optional[str],
) -> List[Run]:
    if user.global_role == GlobalRole.ADMIN:
        projects = await list_project_models(session=session)
    else:
        projects = await list_user_project_models(session=session, user=user)
    if project_name:
        projects = [p for p in projects if p.name == project_name]
    runs = []
    for project in projects:
        project_runs = await list_project_runs(
            session=session,
            project=project,
            repo_id=repo_id,
        )
        runs.extend(map(run_model_to_run, project_runs))
    return sorted(runs, key=lambda r: r.submitted_at, reverse=True)


async def list_project_runs(
    session: AsyncSession,
    project: ProjectModel,
    repo_id: Optional[str],
) -> List[RunModel]:
    filters = [
        RunModel.project_id == project.id,
        RunModel.deleted == False,
    ]
    if repo_id is not None:
        repo = await repos_services.get_repo_model(
            session=session,
            project=project,
            repo_id=repo_id,
        )
        if repo is None:
            raise RepoDoesNotExistError.with_id(repo_id)
        filters.append(RunModel.repo_id == repo.id)
    res = await session.execute(
        select(RunModel).where(*filters).options(joinedload(RunModel.user))
    )
    run_models = res.scalars().all()
    runs = []
    for r in run_models:
        try:
            runs.append(run_model_to_run(r))
        except pydantic.ValidationError:
            pass
    if len(run_models) > len(runs):
        logger.debug(
            "Can't load %s runs from project %s", len(run_models) - len(runs), project.name
        )
    return runs


async def get_run(
    session: AsyncSession,
    project: ProjectModel,
    run_name: str,
) -> Optional[Run]:
    res = await session.execute(
        select(RunModel)
        .where(
            RunModel.project_id == project.id,
            RunModel.run_name == run_name,
            RunModel.deleted == False,
        )
        .options(joinedload(RunModel.user))
    )
    run_model = res.scalar()
    if run_model is None:
        return None
    return run_model_to_run(run_model)


async def get_run_plan_by_requirements(
    project: ProjectModel, profile: Profile
) -> Tuple[Requirements, List[Tuple[Backend, InstanceOfferWithAvailability]]]:
    backends = await backends_services.get_project_backends(project=project)
    if profile.backends is not None:
        backends = [b for b in backends if b.TYPE in profile.backends]

    spot_policy = profile.spot_policy or SpotPolicy.AUTO  # TODO: improve
    requirements = Requirements(
        cpus=profile.resources.cpu,
        memory_mib=profile.resources.memory,
        gpus=None,
        shm_size_mib=profile.resources.shm_size,
        max_price=profile.max_price,
        spot=None if spot_policy == SpotPolicy.AUTO else (spot_policy == SpotPolicy.SPOT),
    )
    if profile.resources.gpu:
        requirements.gpus = GpusRequirements(
            count=profile.resources.gpu.count,
            memory_mib=profile.resources.gpu.memory,
            name=profile.resources.gpu.name,
            total_memory_mib=profile.resources.gpu.total_memory,
            compute_capability=profile.resources.gpu.compute_capability,
        )

    offers = await backends_services.get_instance_offers(
        backends=backends,
        requirements=requirements,
        exclude_not_available=False,
    )

    return requirements, offers


async def create_instance(
    project: ProjectModel, user: UserModel, pool_name: str, instance_name: str, profile: Profile
):
    _, offers = await get_run_plan_by_requirements(project, profile)

    ssh_key = SSHKeys(
        public=project.ssh_public_key.strip(),
        private=project.ssh_private_key.strip(),
    )
    instance_config = InstanceConfiguration(
        instance_name=instance_name,
        pool_name=pool_name,
        ssh_keys=[ssh_key],
        job_docker_config=DockerConfig(
            image=parse_image_name(get_default_image(get_default_python_verison())),
            registry_auth=None,
        ),
    )

    for backend, instance_offer in offers:

        logger.debug(
            "trying %s in %s/%s for $%0.4f per hour",
            instance_offer.instance.name,
            instance_offer.backend.value,
            instance_offer.region,
            instance_offer.price,
        )
        try:
            launched_instance_info: LaunchedInstanceInfo = await run_async(
                backend.compute().create_instance,
                project,
                user,
                instance_offer,
                instance_config,
            )
        except BackendError as e:
            logger.warning(
                "%s launch in %s/%s failed: %s",
                instance_offer.instance.name,
                instance_offer.backend.value,
                instance_offer.region,
                repr(e),
            )
            continue
        else:
            job_provisioning_data = JobProvisioningData(
                backend=backend.TYPE,
                instance_type=instance_offer.instance,
                instance_id=launched_instance_info.instance_id,
                pool_id=pool_name,
                hostname=launched_instance_info.ip_address,
                region=launched_instance_info.region,
                price=instance_offer.price,
                username=launched_instance_info.username,
                ssh_port=launched_instance_info.ssh_port,
                dockerized=launched_instance_info.dockerized,
                backend_data=launched_instance_info.backend_data,
            )

            return (job_provisioning_data, instance_offer)
    return (None, None)


async def get_run_plan(
    session: AsyncSession,
    project: ProjectModel,
    user: UserModel,
    run_spec: RunSpec,
) -> RunPlan:
    backends = await backends_services.get_project_backends(project=project)
    if run_spec.profile.backends is not None:
        backends = [b for b in backends if b.TYPE in run_spec.profile.backends]
    run_name = run_spec.run_name  # preserve run_name
    run_spec.run_name = "dry-run"  # will regenerate jobs on submission
    jobs = get_jobs_from_run_spec(run_spec)
    job_plans = []
    for job in jobs:
        # TODO: use the job.pool_name to select an offer
        requirements = job.job_spec.requirements
        offers = await backends_services.get_instance_offers(
            backends=backends,
            requirements=requirements,
            exclude_not_available=False,
        )
        for backend, offer in offers:
            offer.backend = backend.TYPE
        offers = [offer for _, offer in offers]
        job_plan = JobPlan(
            job_spec=job.job_spec,
            offers=offers[:50],
            total_offers=len(offers),
            max_price=max((offer.price for offer in offers), default=None),
        )
        job_plans.append(job_plan)
    run_spec.run_name = run_name  # restore run_name
    run_plan = RunPlan(
        project_name=project.name, user=user.name, run_spec=run_spec, job_plans=job_plans
    )
    return run_plan


async def submit_run(
    session: AsyncSession,
    user: UserModel,
    project: ProjectModel,
    run_spec: RunSpec,
) -> Run:
    repo = await repos_services.get_repo_model(
        session=session,
        project=project,
        repo_id=run_spec.repo_id,
    )
    if repo is None:
        raise RepoDoesNotExistError.with_id(run_spec.repo_id)
    backends = await backends_services.get_project_backends(project)
    if len(backends) == 0:
        raise ServerClientError("No backends configured")

    if run_spec.run_name is None:
        run_spec.run_name = await _generate_run_name(
            session=session,
            project=project,
        )
    else:
        await delete_runs(session=session, project=project, runs_names=[run_spec.run_name])

    pool_name = (
        DEFAULT_POOL_NAME if run_spec.profile.pool_name is None else run_spec.profile.pool_name
    )

    # create pool
    pools = (
        await session.scalars(
            select(PoolModel).where(PoolModel.name == pool_name, PoolModel.deleted == False)
        )
    ).all()
    if not pools:
        await create_pool_model(session, project, pool_name)

    run_model = RunModel(
        id=uuid.uuid4(),
        project_id=project.id,
        repo_id=repo.id,
        user=user,
        run_name=run_spec.run_name,
        submitted_at=common_utils.get_current_datetime(),
        status=JobStatus.SUBMITTED,
        run_spec=run_spec.json(),
    )
    session.add(run_model)

    jobs = get_jobs_from_run_spec(run_spec)
    if run_spec.configuration.type == "service":
        await gateways.register_service_jobs(session, project, run_spec.run_name, jobs)
    for job in jobs:
        job.job_spec.pool_name = pool_name
        job_model = create_job_model_for_new_submission(
            run_model=run_model,
            job=job,
            status=JobStatus.SUBMITTED,
        )
        session.add(job_model)
    await session.commit()
    await session.refresh(run_model)

    run = run_model_to_run(run_model)
    return run


def create_job_model_for_new_submission(
    run_model: RunModel,
    job: Job,
    status: JobStatus,
) -> JobModel:
    now = common_utils.get_current_datetime()
    return JobModel(
        id=uuid.uuid4(),
        project_id=run_model.project_id,
        run_id=run_model.id,
        run_name=run_model.run_name,
        job_num=job.job_spec.job_num,
        job_name=job.job_spec.job_name,
        submission_num=len(job.job_submissions),
        submitted_at=now,
        last_processed_at=now,
        status=status,
        error_code=None,
        job_spec_data=job.job_spec.json(),
        job_provisioning_data=None,
    )


async def stop_runs(
    session: AsyncSession,
    project: ProjectModel,
    runs_names: List[str],
    abort: bool,
):
    new_status = JobStatus.TERMINATED
    if abort:
        new_status = JobStatus.ABORTED

    res = await session.execute(
        select(JobModel).where(
            JobModel.project_id == project.id,
            JobModel.run_name.in_(runs_names),
            JobModel.status.not_in(JobStatus.finished_statuses()),
        )
    )
    job_models = res.scalars().all()
    for job_model in job_models:
        await stop_job(
            session=session,
            project=project,
            job_model=job_model,
            new_status=new_status,
        )


async def delete_runs(
    session: AsyncSession,
    project: ProjectModel,
    runs_names: List[str],
):
    res = await session.execute(
        select(RunModel).where(
            RunModel.project_id == project.id, RunModel.run_name.in_(runs_names)
        )
    )
    run_models = res.scalars().all()
    runs = [run_model_to_run(r) for r in run_models]
    active_runs = [r for r in runs if not r.status.is_finished()]
    if len(active_runs) > 0:
        raise ServerClientError(
            msg=f"Cannot delete active runs: {[r.run_spec.run_name for r in active_runs]}"
        )
    await session.execute(
        update(RunModel)
        .where(
            RunModel.project_id == project.id,
            RunModel.run_name.in_(runs_names),
        )
        .values(deleted=True)
    )
    await session.commit()


def run_model_to_run(run_model: RunModel, include_job_submissions: bool = True) -> Run:
    jobs: List[Job] = []
    # JobSpec from JobConfigurator doesn't have gateway information for `service` type
    run_jobs = sorted(run_model.jobs, key=lambda j: (j.job_num, j.submission_num))
    for job_num, job_submissions in itertools.groupby(run_jobs):
        job_spec = None
        submissions = []
        for job_model in job_submissions:
            if job_spec is None:
                job_spec = JobSpec.parse_raw(job_model.job_spec_data)
            if include_job_submissions:
                submissions.append(job_model_to_job_submission(job_model))
        if job_spec is not None:
            jobs.append(Job(job_spec=job_spec, job_submissions=submissions))

    run_spec = RunSpec.parse_raw(run_model.run_spec)

    latest_job_submission = None
    if include_job_submissions:
        latest_job_submission = jobs[0].job_submissions[-1]

    run = Run(
        id=run_model.id,
        project_name=run_model.project.name,
        user=run_model.user.name,
        submitted_at=run_model.submitted_at.replace(tzinfo=timezone.utc),
        status=get_run_status(jobs),
        run_spec=run_spec,
        jobs=jobs,
        latest_job_submission=latest_job_submission,
    )
    run.cost = _get_run_cost(run)
    run.service = _get_run_service(run)
    return run


def get_run_status(jobs: List[Job]) -> JobStatus:
    job = jobs[0]
    if len(job.job_submissions) == 0:
        return JobStatus.SUBMITTED
    return job.job_submissions[-1].status


_PROJECTS_TO_RUN_NAMES_LOCK = {}


async def _generate_run_name(
    session: AsyncSession,
    project: ProjectModel,
) -> str:
    lock = _PROJECTS_TO_RUN_NAMES_LOCK.setdefault(project.name, asyncio.Lock())
    run_name_base = generate_name()
    idx = 1
    async with lock:
        while (
            await get_run(
                session=session,
                project=project,
                run_name=f"{run_name_base}-{idx}",
            )
            is not None
        ):
            idx += 1
        return f"{run_name_base}-{idx}"


def _get_run_cost(run: Run) -> float:
    run_cost = math.fsum(
        _get_job_submission_cost(submission)
        for job in run.jobs
        for submission in job.job_submissions
    )
    return round(run_cost, 4)


def _get_job_submission_cost(job_submission: JobSubmission) -> float:
    if job_submission.job_provisioning_data is None:
        return 0
    duration_hours = job_submission.duration.total_seconds() / 3600
    return job_submission.job_provisioning_data.price * duration_hours


def _get_run_service(run: Run) -> Optional[ServiceInfo]:
    if run.run_spec.configuration.type != "service":
        return None

    gateway = run.jobs[0].job_spec.gateway
    model = None
    if run.run_spec.configuration.model is not None:
        domain = gateway.hostname.split(".", maxsplit=1)[1]
        model = ServiceModelInfo(
            name=run.run_spec.configuration.model.name,
            base_url=f"https://gateway.{domain}",
            type=run.run_spec.configuration.model.type,
        )

    omit_port = (gateway.secure and gateway.public_port == 443) or (
        not gateway.secure and gateway.public_port == 80
    )
    return ServiceInfo(
        url="%s://%s%s"
        % (
            "https" if gateway.secure else "http",
            gateway.hostname,
            "" if omit_port else f":{gateway.public_port}",
        ),
        model=model,
    )


async def abort_runs_of_pool(session: AsyncSession, project_model: ProjectModel, pool_name: str):
    runs = await list_project_runs(session, project_model, repo_id=None)
    active_run_names = []
    for run_model in runs:
        if run_model.status.is_finished():
            continue

        run = run_model_to_run(run_model)
        run_pool_name = run.run_spec.profile.pool_name
        if run_pool_name == pool_name:
            active_run_names.append(run.run_spec.run_name)

    await stop_runs(session, project_model, active_run_names, abort=True)

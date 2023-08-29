import re
from typing import List, Optional

import yaml

from dstack._internal.backend.base import jobs, runners
from dstack._internal.backend.base.compute import Compute
from dstack._internal.backend.base.storage import Storage
from dstack._internal.core.app import AppHead
from dstack._internal.core.artifact import ArtifactHead
from dstack._internal.core.error import BackendValueError
from dstack._internal.core.job import JobErrorCode, JobHead, JobStatus
from dstack._internal.core.run import RequestStatus, RunHead, generate_remote_run_name_prefix
from dstack._internal.utils.common import get_milliseconds_since_epoch


def create_run(storage: Storage, run_name: str) -> str:
    if run_name is None:
        return _generate_random_run_name(storage)
    _validate_run_name(run_name)
    key = _get_run_name_filename(run_name)
    obj = storage.get_object(key)
    if obj is None:
        storage.put_object(key=key, content=yaml.dump({"count": 1}))
    return run_name


def get_run_heads(
    storage: Storage,
    compute: Compute,
    job_heads: List[JobHead],
    include_request_heads: bool,
) -> List[RunHead]:
    runs_by_id = {}
    for job_head in job_heads:
        run_id = ",".join([job_head.run_name, job_head.workflow_name or ""])
        if run_id not in runs_by_id:
            runs_by_id[run_id] = _create_run(
                storage,
                compute,
                job_head,
                include_request_heads,
            )
        else:
            run = runs_by_id[run_id]
            _update_run(
                storage,
                compute,
                run,
                job_head,
                include_request_heads,
            )
    run_heads = list(sorted(runs_by_id.values(), key=lambda r: r.submitted_at, reverse=True))
    return run_heads


def _generate_random_run_name(storage: Storage):
    name = generate_remote_run_name_prefix()
    run_name_index = _next_run_name_index(storage, name)
    return f"{name}-{run_name_index}"


def _next_run_name_index(storage: Storage, run_name: str) -> int:
    count = 0
    key = _get_run_name_filename(run_name)
    obj = storage.get_object(key)
    if obj is None:
        storage.put_object(key=key, content=yaml.dump({"count": 1}))
        return 1
    count = yaml.load(obj, yaml.FullLoader)["count"]
    storage.put_object(key=key, content=yaml.dump({"count": count + 1}))
    return count + 1


def _validate_run_name(run_name: str):
    if re.match(r"^[a-zA-Z0-9_-]{5,100}$", run_name) is None:
        raise BackendValueError(
            "Invalid run name. "
            "Run name may include alphanumeric characters, dashes, and underscores, "
            "and its length should be between 5 and 100 characters."
        )


def _create_run(
    storage: Storage,
    compute: Compute,
    job_head: JobHead,
    include_request_heads: bool,
) -> RunHead:
    app_heads = (
        list(
            map(
                lambda app_name: AppHead(job_id=job_head.job_id, app_name=app_name),
                job_head.app_names,
            )
        )
        if job_head.app_names
        else None
    )
    artifact_heads = (
        list(
            map(
                lambda artifact_path: ArtifactHead(
                    job_id=job_head.job_id, artifact_path=artifact_path
                ),
                job_head.artifact_paths,
            )
        )
        if job_head.artifact_paths
        else None
    )
    request_heads = None
    if include_request_heads and job_head.status.is_unfinished():
        if request_heads is None:
            request_heads = []
        job = jobs.get_job(storage, job_head.repo_ref.repo_id, job_head.job_id)
        request_id = job.request_id
        if request_id is None and job.runner_id is not None:
            runner = runners.get_runner(storage, job.runner_id)
            if not (runner is None):
                request_id = runner.request_id
        request_head = compute.get_request_head(job, request_id)
        request_heads.append(request_head)
        if request_head.status == RequestStatus.NO_CAPACITY:
            if job.retry_active():
                interrupted_job_new_status = JobStatus.PENDING
            else:
                interrupted_job_new_status = JobStatus.FAILED
                job.error_code = JobErrorCode.INTERRUPTED_BY_NO_CAPACITY
            job.status = job_head.status = interrupted_job_new_status
            jobs.update_job(storage, job)
        elif request_head.status == RequestStatus.TERMINATED:
            # We should check the job status again, to ensure it hasn't been updated just
            # before the instance was terminated
            job = jobs.get_job(storage, job_head.repo_ref.repo_id, job_head.job_id)
            if job.status.is_unfinished():
                job.status = job_head.status = JobStatus.FAILED
                job.error_code = JobErrorCode.INSTANCE_TERMINATED
                jobs.update_job(storage, job)
    run_head = RunHead(
        run_name=job_head.run_name,
        workflow_name=job_head.workflow_name,
        provider_name=job_head.provider_name,
        configuration_path=job_head.configuration_path,
        hub_user_name=job_head.hub_user_name,
        artifact_heads=artifact_heads or None,
        status=job_head.status,
        submitted_at=job_head.submitted_at,
        tag_name=job_head.tag_name,
        app_heads=app_heads,
        request_heads=request_heads,
        job_heads=[job_head],
    )
    return run_head


def _update_run(
    storage: Storage,
    compute: Compute,
    run: RunHead,
    job_head: JobHead,
    include_request_heads: bool,
):
    run.submitted_at = min(run.submitted_at, job_head.submitted_at)
    if job_head.artifact_paths:
        if run.artifact_heads is None:
            run.artifact_heads = []
        run.artifact_heads.extend(
            list(
                map(
                    lambda artifact_path: ArtifactHead(
                        job_id=job_head.job_id, artifact_path=artifact_path
                    ),
                    job_head.artifact_paths,
                )
            )
        )
    if job_head.app_names:
        if run.app_heads is None:
            run.app_heads = []
        run.app_heads.extend(
            list(
                map(
                    lambda app_name: AppHead(job_id=job_head.job_id, app_name=app_name),
                    job_head.app_names,
                )
            )
        )
    if job_head.status.is_unfinished():
        if include_request_heads:
            if run.request_heads is None:
                run.request_heads = []
            job = jobs.get_job(storage, job_head.repo_ref.repo_id, job_head.job_id)
            request_id = job.request_id
            if request_id is None and job.runner_id is not None:
                runner = runners.get_runner(storage, job.runner_id)
                request_id = runner.request_id
            request_head = compute.get_request_head(job, request_id)
            run.request_heads.append(request_head)
            if request_head.status == RequestStatus.NO_CAPACITY:
                if job.retry_active():
                    interrupted_job_new_status = JobStatus.PENDING
                else:
                    interrupted_job_new_status = JobStatus.FAILED
                    job.error_code = JobErrorCode.INTERRUPTED_BY_NO_CAPACITY
                job.status = job_head.status = interrupted_job_new_status
                jobs.update_job(storage, job)
            elif request_head.status == RequestStatus.TERMINATED:
                job = jobs.get_job(storage, job_head.repo_ref.repo_id, job_head.job_id)
                if job.status.is_unfinished():
                    job.status = job_head.status = JobStatus.FAILED
                    job.error_code = JobErrorCode.INSTANCE_TERMINATED
                    jobs.update_job(storage, job)
        run.status = job_head.status
    run.job_heads.append(job_head)


def _get_run_name_filename(run_name: str) -> str:
    return f"run_names/{run_name}.yaml"

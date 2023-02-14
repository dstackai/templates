import os
from pathlib import Path
from typing import List, Optional

from tqdm import tqdm

from dstack.backend.base import jobs
from dstack.backend.base.storage import Storage
from dstack.core.artifact import Artifact
from dstack.core.job import Job
from dstack.core.repo import RepoAddress


def list_run_artifact_files(
    storage: Storage, repo_address: RepoAddress, run_name: str
) -> List[Artifact]:
    jobs_list = jobs.list_jobs(storage, repo_address, run_name)
    artifacts = []
    for job in jobs_list:
        job_artifacts_dir = _get_job_artifacts_dir(repo_address, job.job_id)
        for artifact_path in job.artifact_paths:
            artifact_path = os.path.join(artifact_path, "")
            job_artifact_files_path = os.path.join(job_artifacts_dir, artifact_path)
            artifact_files = storage.list_files(job_artifact_files_path)
            artifact = Artifact(
                job_id=job.job_id,
                name=artifact_path,
                files=artifact_files,
            )
            artifacts.append(artifact)
    return artifacts


def download_run_artifact_files(
    storage: Storage,
    repo_address: RepoAddress,
    run_name: str,
    artifacts_dest_dir: Optional[str],
):
    if artifacts_dest_dir is None:
        artifacts_dest_dir = os.getcwd()
    artifacts = list_run_artifact_files(storage, repo_address, run_name)
    for artifact in artifacts:
        total_size = sum(f.filesize_in_bytes for f in artifact.files)
        with tqdm(
            total=total_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=f"Downloading artifact '{artifact.name}'",
        ) as pbar:

            def callback(size):
                pbar.update(size)

            for file in artifact.files:
                artifacts_dir = _get_job_artifacts_dir(repo_address, artifact.job_id)
                source_path = os.path.join(artifacts_dir, artifact.name, file.filepath)
                dest_path = os.path.join(
                    artifacts_dest_dir, artifact.job_id, artifact.name, file.filepath
                )
                Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
                storage.download_file(source_path, dest_path, callback)


def upload_job_artifact_files(
    storage: Storage,
    repo_address: RepoAddress,
    job_id: str,
    artifact_name: str,
    local_path: Path,
):
    artifacts_dir = _get_job_artifacts_dir(repo_address, job_id)
    total_size = 0
    for root, sub_dirs, files in os.walk(local_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            file_size = os.path.getsize(file_path)
            total_size += file_size
    with tqdm(
        total=total_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=f"Uploading artifact '{artifact_name}'",
    ) as pbar:

        def callback(size):
            pbar.update(size)

        for root, sub_dirs, files in os.walk(local_path):
            for filename in files:
                filepath = os.path.join(root, filename)
                source_path = filepath
                dest_path = os.path.join(
                    artifacts_dir, artifact_name, Path(filepath).relative_to(local_path)
                )
                storage.upload_file(source_path, dest_path, callback)


def _get_artifacts_dir(repo_address: RepoAddress) -> str:
    return f"artifacts/{repo_address.path()}/"


def _get_job_artifacts_dir(repo_address: RepoAddress, job_id: str) -> str:
    return f"{_get_artifacts_dir(repo_address)}{job_id}/"

from typing import Generator

from google.cloud import logging

from dstack.backend.base import jobs
from dstack.backend.base.logs import replace_logs_host
from dstack.backend.base.storage import Storage
from dstack.core.log_event import LogEvent, LogEventSource
from dstack.core.repo import RepoAddress


class GCPLogging:
    def __init__(self, project_id: str, bucket_name: str):
        self.project_id = project_id
        self.bucket_name = bucket_name
        self.logging_client = logging.Client(project=project_id)

    def poll_logs(
        self,
        storage: Storage,
        repo_address: RepoAddress,
        run_name: str,
    ) -> Generator[LogEvent, None, None]:
        log_name = f"dstack-{self.bucket_name}-{run_name}"
        logger = self.logging_client.logger(log_name)
        log_entries = logger.list_entries()
        for log_entry in log_entries:
            yield log_entry_to_log_event(storage, repo_address, log_entry)


def log_entry_to_log_event(
    storage: Storage,
    repo_address: RepoAddress,
    log_entry: logging.LogEntry,
) -> LogEvent:
    job_id = log_entry.payload["job_id"]
    log = log_entry.payload["log"]
    job = jobs.get_job(storage, repo_address, job_id)
    log = replace_logs_host(log, job)
    return LogEvent(
        event_id=log_entry.insert_id,
        timestamp=log_entry.timestamp,
        job_id=job_id,
        log_message=log,
        log_source=LogEventSource.STDOUT
        if log_entry.payload["source"] == "stdout"
        else LogEventSource.STDERR,
    )

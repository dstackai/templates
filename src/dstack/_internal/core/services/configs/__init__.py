import json
import os.path
from pathlib import Path
from typing import Optional, Tuple

import filelock
import yaml
from pydantic import ValidationError

from dstack._internal.core.errors import DstackError
from dstack._internal.core.models.config import GlobalConfig, ProjectConfig, RepoConfig
from dstack._internal.core.models.repos.base import RepoType
from dstack._internal.utils.common import get_dstack_dir
from dstack._internal.utils.path import PathLike
from dstack.api.server import APIClient


def get_api_client(project_name: Optional[str] = None) -> Tuple[APIClient, str]:
    config = ConfigManager()
    project = config.get_project_config(project_name)
    if project is None:
        if project_name is not None:
            raise DstackError(f"Project {project_name} is not configured")
        raise DstackError(f"No default project")
    return APIClient(project.url, project.token), project.name


class ConfigManager:
    config: GlobalConfig

    def __init__(self, dstack_dir: Optional[PathLike] = None):
        self.dstack_dir = Path(dstack_dir) if dstack_dir else get_dstack_dir()
        self.config_filepath = self.dstack_dir / "config.yaml"
        self.load()

    def get_project_config(self, name: Optional[str] = None) -> Optional[ProjectConfig]:
        for project in self.config.projects:
            if name is None and project.default:
                return project
            if project.name == name:
                return project
        return None

    def save(self):
        self.config_filepath.parent.mkdir(parents=True, exist_ok=True)
        with self.config_filepath.open("w") as f:
            # hack to convert enums to strings, etc.
            yaml.dump(json.loads(self.config.json()), f)

    def load(self):
        try:
            with open(self.config_filepath, "r") as f:
                config = yaml.safe_load(f)
            self.config = GlobalConfig.parse_obj(config)
        except (FileNotFoundError, ValidationError):
            self.config = GlobalConfig()

    def save_repo_config(
        self, repo_path: PathLike, repo_id: str, repo_type: RepoType, ssh_key_path: PathLike
    ):
        self.config_filepath.parent.mkdir(parents=True, exist_ok=True)
        with filelock.FileLock(str(self.config_filepath) + ".lock"):
            self.load()
            repo_path = os.path.abspath(repo_path)
            ssh_key_path = os.path.abspath(ssh_key_path)
            for repo in self.config.repos:
                if repo.path == repo_path:
                    repo.repo_id = repo_id
                    repo.repo_type = repo_type
                    repo.ssh_key_path = ssh_key_path
                    break
            else:
                self.config.repos.append(
                    RepoConfig(
                        path=repo_path,
                        repo_id=repo_id,
                        repo_type=repo_type,
                        ssh_key_path=ssh_key_path,
                    )
                )
            self.save()

    def get_repo_config(self, repo_path: PathLike) -> Optional[RepoConfig]:
        repo_path = os.path.abspath(repo_path)
        # TODO look at parent directories
        for repo in self.config.repos:
            if repo.path == repo_path:
                return repo
        return None

    @property
    def dstack_key_path(self) -> Path:
        return self.dstack_dir / "ssh/id_rsa"

    @property
    def dstack_ssh_config_path(self) -> Path:
        return self.dstack_dir / "ssh/config"

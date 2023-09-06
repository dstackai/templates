from typing import Union

from dstack._internal.core.repo.base import Repo, RepoData, RepoProtocol, RepoRef
from dstack._internal.core.repo.head import Repo
from dstack._internal.core.repo.local import LocalRepo, LocalRepoData, LocalRepoInfo
from dstack._internal.core.repo.remote import (
    RemoteRepo,
    RemoteRepoCredentials,
    RemoteRepoData,
    RemoteRepoInfo,
)
from dstack._internal.core.repo.spec import RepoSpec

AnyRepoData = Union[RemoteRepoData, LocalRepoData]

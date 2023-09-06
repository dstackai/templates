from typing import List

from dstack._internal.core.secret import Secret
from dstack._internal.server.schemas.common import RepoRequest


class ListSecretsRequest(RepoRequest):
    pass


class GetSecretsRequest(RepoRequest):
    pass


class AddSecretRequest(RepoRequest):
    secret: Secret


class DeleteSecretsRequest(RepoRequest):
    secrets_names: List[str]

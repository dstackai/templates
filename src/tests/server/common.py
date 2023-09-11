import json
import uuid
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from dstack._internal.core.models.users import GlobalRole
from dstack._internal.server.db import reuse_or_make_session
from dstack._internal.server.models import ProjectModel, UserModel


def get_auth_headers(token: str) -> Dict:
    return {"Authorization": f"Bearer {token}"}


async def create_user(
    session: AsyncSession,
    name: str = "test_user",
    global_role: GlobalRole = GlobalRole.ADMIN,
    token: Optional[str] = None,
) -> UserModel:
    if token is None:
        token = str(uuid.uuid4())
    user = UserModel(
        name=name,
        global_role=global_role,
        token=token,
    )
    session.add(user)
    await session.commit()
    return user


async def create_project(
    session: AsyncSession,
    name: str = "test_project",
    ssh_private_key: str = "",
    ssh_public_key: str = "",
) -> ProjectModel:
    project = ProjectModel(
        name=name,
        ssh_private_key=ssh_private_key,
        ssh_public_key=ssh_public_key,
    )
    session.add(project)
    await session.commit()
    return project


# async def create_backend(
#     project_name: str,
#     backend_type: str = "aws",
#     config: Optional[Dict] = None,
#     auth: Optional[Dict] = None,
# ) -> Backend:
#     if config is None:
#         config = {
#             "regions": ["eu-west-1"],
#             "s3_bucket_name": "dstack-test-eu-west-1",
#             "ec2_subnet_id": None,
#         }
#     if auth is None:
#         auth = {
#             "type": "access_key",
#             "access_key": "test_access_key",
#             "secret_key": "test_secret_key",
#         }
#     backend = Backend(
#         project_name=project_name,
#         type=backend_type,
#         name=backend_type,
#         config=json.dumps(config),
#         auth=json.dumps(auth),
#     )
#     await ProjectManager._create_backend(backend)
#     return backend

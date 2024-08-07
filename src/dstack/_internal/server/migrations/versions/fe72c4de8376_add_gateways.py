"""Add gateways

Revision ID: fe72c4de8376
Revises: 252d3743b641
Create Date: 2023-09-27 17:42:15.696906

"""

import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op

# revision identifiers, used by Alembic.
revision = "fe72c4de8376"
down_revision = "252d3743b641"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "gateways",
        sa.Column("id", sqlalchemy_utils.types.uuid.UUIDType(binary=False), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("ip_address", sa.String(length=100), nullable=False),
        sa.Column("instance_id", sa.String(length=100), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=False),
        sa.Column("wildcard_domain", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "project_id", sqlalchemy_utils.types.uuid.UUIDType(binary=False), nullable=False
        ),
        sa.Column(
            "backend_id", sqlalchemy_utils.types.uuid.UUIDType(binary=False), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["backend_id"],
            ["backends.id"],
            name=op.f("fk_gateways_backend_id_backends"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_gateways_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gateways")),
        sa.UniqueConstraint("project_id", "name", name="uq_gateways_project_id_name"),
    )
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "default_gateway_id",
                sqlalchemy_utils.types.uuid.UUIDType(binary=False),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_projects_default_gateway_id_gateways"),
            "gateways",
            ["default_gateway_id"],
            ["id"],
            ondelete="SET NULL",
            use_alter=True,
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_projects_default_gateway_id_gateways"), type_="foreignkey"
        )
        batch_op.drop_column("default_gateway_id")

    op.drop_table("gateways")
    # ### end Alembic commands ###

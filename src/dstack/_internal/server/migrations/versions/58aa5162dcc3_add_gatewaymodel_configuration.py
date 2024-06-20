"""Add GatewayModel.configuration

Revision ID: 58aa5162dcc3
Revises: 1e3fb39ef74b
Create Date: 2024-05-15 11:04:58.848554

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "58aa5162dcc3"
down_revision = "1e3fb39ef74b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("gateways", schema=None) as batch_op:
        batch_op.add_column(sa.Column("configuration", sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("gateways", schema=None) as batch_op:
        batch_op.drop_column("configuration")

    # ### end Alembic commands ###

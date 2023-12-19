"""Do not delete projects and runs

Revision ID: 48ad3ecbaea2
Revises: e6391ca6a264
Create Date: 2023-12-19 15:55:50.386918

"""
import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op

# revision identifiers, used by Alembic.
revision = "48ad3ecbaea2"
down_revision = "e6391ca6a264"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deleted", sa.Boolean(), nullable=True))

    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deleted", sa.Boolean(), nullable=True))

    op.execute(sa.sql.text("UPDATE runs SET deleted = FALSE"))
    op.execute(sa.sql.text("UPDATE projects SET deleted = FALSE"))

    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.alter_column("deleted", nullable=False)

    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.alter_column("deleted", nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_column("deleted")

    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("deleted")

    # ### end Alembic commands ###

"""Add checked_in column to registrations

Revision ID: f9e0150414d0
Revises: b92f9a1b9888
Create Date: 2025-03-04 10:52:40.442985

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f9e0150414d0'
down_revision = 'b92f9a1b9888'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('registrations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('checked_in', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('registrations', schema=None) as batch_op:
        batch_op.drop_column('checked_in')

    # ### end Alembic commands ###

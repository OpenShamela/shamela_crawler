"""Add author table

Revision ID: 7dd17bdb5535
Revises: b0e9d30fac5c
Create Date: 2024-03-25 18:16:50.541891

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '7dd17bdb5535'
down_revision = 'b0e9d30fac5c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'authors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('bio', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('authors')
    # ### end Alembic commands ###

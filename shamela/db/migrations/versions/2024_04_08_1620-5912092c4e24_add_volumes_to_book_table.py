"""Add volumes to book table

Revision ID: 5912092c4e24
Revises: b3f0147f3861
Create Date: 2024-04-08 16:20:06.544707

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '5912092c4e24'
down_revision = 'b3f0147f3861'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('books', sa.Column('volumes', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('books', 'volumes')
    # ### end Alembic commands ###
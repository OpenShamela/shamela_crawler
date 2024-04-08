"""Add pages to book table

Revision ID: b3f0147f3861
Revises: 560ba3da89ae
Create Date: 2024-04-08 02:26:53.518489

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b3f0147f3861'
down_revision = '560ba3da89ae'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('books', sa.Column('pages', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('books', 'pages')

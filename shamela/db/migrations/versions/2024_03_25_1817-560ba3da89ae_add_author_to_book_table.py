"""Add author to book table

Revision ID: 560ba3da89ae
Revises: 7dd17bdb5535
Create Date: 2024-03-25 18:17:41.046043

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '560ba3da89ae'
down_revision = '7dd17bdb5535'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('books') as batch_op:
        batch_op.add_column(sa.Column('author_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_books_author_id', 'authors', ['author_id'], ['id'])
        batch_op.drop_column('author')


def downgrade() -> None:
    with op.batch_alter_table('books') as batch_op:
        batch_op.add_column(sa.Column('author', sa.VARCHAR(), nullable=True))
        batch_op.create_foreign_key('fk_books_author', 'authors', ['author'], ['id'])
        batch_op.drop_column('author_id')

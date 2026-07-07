"""add books, documents tables and users.is_admin

Revision ID: d11085afd4d2
Revises: 5f8884470c81
Create Date: 2026-07-06 16:30:09.462606

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd11085afd4d2'
down_revision: Union[str, Sequence[str], None] = '5f8884470c81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 新增 is_admin 列到 users 表
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))

    # 新建 books 表
    op.create_table('books',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('author', sa.String(length=128), nullable=False),
        sa.Column('isbn', sa.String(length=20), nullable=True),
        sa.Column('publisher', sa.String(length=128), nullable=True),
        sa.Column('publish_year', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('location', sa.String(length=128), nullable=True),
        sa.Column('total', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('available', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_books_title'), 'books', ['title'], unique=False)
    op.create_index(op.f('ix_books_isbn'), 'books', ['isbn'], unique=True)
    op.create_index(op.f('ix_books_category'), 'books', ['category'], unique=False)

    # 新建 documents 表
    op.create_table('documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('filename', sa.String(length=256), nullable=False),
        sa.Column('source_type', sa.Enum('policy', 'rule', 'faq', 'other', name='doc_source_type_enum'), nullable=False),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('documents')
    op.drop_index(op.f('ix_books_category'), table_name='books')
    op.drop_index(op.f('ix_books_isbn'), table_name='books')
    op.drop_index(op.f('ix_books_title'), table_name='books')
    op.drop_table('books')
    op.drop_column('users', 'is_admin')
    op.execute('DROP TYPE IF EXISTS doc_source_type_enum')

"""Add chunk embeddings.

Revision ID: d444996bc941
Revises: af6b5f2bc004
"""

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column

revision: str = "d444996bc941"
down_revision: str | Sequence[str] | None = "af6b5f2bc004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_chunks", Column("embedding", Vector(1536), nullable=True))


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding")

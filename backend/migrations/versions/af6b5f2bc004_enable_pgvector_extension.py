"""Enable the pgvector extension.

Revision ID: af6b5f2bc004
Revises: f93aeb93129d

"""

from collections.abc import Sequence

from alembic import op

revision: str = "af6b5f2bc004"
down_revision: str | Sequence[str] | None = "f93aeb93129d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION vector")

"""add chunked document status

Revision ID: f93aeb93129d
Revises: df748e05fd44
Create Date: 2026-10-27 14:37:34.188739

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f93aeb93129d"
down_revision: str | Sequence[str] | None = "df748e05fd44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_documents_document_status"),
        "documents",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_documents_document_status"),
        "documents",
        "status IN ('uploaded', 'processing', 'extracted', 'chunked', 'ready', 'failed')",
    )


def downgrade() -> None:
    op.execute("UPDATE documents SET status = 'extracted' WHERE status = 'chunked'")
    op.drop_constraint(
        op.f("ck_documents_document_status"),
        "documents",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_documents_document_status"),
        "documents",
        "status IN ('uploaded', 'processing', 'extracted', 'ready', 'failed')",
    )

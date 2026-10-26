"""Add extracted document status."""

from collections.abc import Sequence

from alembic import op

revision: str = "59e183d5978b"
down_revision: str | Sequence[str] | None = "e225baf6eb6b"
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
        "status IN ('uploaded', 'processing', 'extracted', 'ready', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_documents_document_status"),
        "documents",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_documents_document_status"),
        "documents",
        "status IN ('uploaded', 'processing', 'ready', 'failed')",
    )

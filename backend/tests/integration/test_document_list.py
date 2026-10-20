from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from documind.models.document import Document, DocumentStatus

pytestmark = pytest.mark.integration


def test_list_orders_documents_and_pages_without_duplicates(
    authenticated_client: TestClient,
    other_authenticated_client: TestClient,
    integration_database_engine: Engine,
) -> None:
    document_ids = sorted([uuid4(), uuid4(), uuid4()], reverse=True)
    other_document_id = uuid4()
    owner_id = UUID(authenticated_client.get("/auth/me").json()["id"])
    other_owner_id = UUID(other_authenticated_client.get("/auth/me").json()["id"])
    created_at = datetime(2099, 1, 1, tzinfo=UTC)

    try:
        with Session(integration_database_engine) as session:
            session.add_all(
                Document(
                    id=document_id,
                    owner_id=owner_id,
                    original_filename=f"list-{document_id}.pdf",
                    storage_key=f"documents/{document_id}.pdf",
                    content_type="application/pdf",
                    size_bytes=100,
                    status=DocumentStatus.UPLOADED,
                    created_at=created_at,
                )
                for document_id in document_ids
            )
            session.add(
                Document(
                    id=other_document_id,
                    owner_id=other_owner_id,
                    original_filename="other-user.pdf",
                    storage_key=f"documents/{other_document_id}.pdf",
                    content_type="application/pdf",
                    size_bytes=100,
                    status=DocumentStatus.UPLOADED,
                    created_at=datetime(2100, 1, 1, tzinfo=UTC),
                )
            )
            session.commit()

        first_page = authenticated_client.get("/documents", params={"limit": 2, "offset": 0})
        second_page = authenticated_client.get("/documents", params={"limit": 2, "offset": 2})

        assert first_page.status_code == 200
        assert second_page.status_code == 200
        assert first_page.json()["has_more"] is True
        assert [item["id"] for item in first_page.json()["items"]] == [
            str(document_id) for document_id in document_ids[:2]
        ]
        assert second_page.json()["items"][0]["id"] == str(document_ids[2])
        assert len(second_page.json()["items"]) == 1
        assert second_page.json()["has_more"] is False
        assert set(item["id"] for item in first_page.json()["items"]).isdisjoint(
            item["id"] for item in second_page.json()["items"]
        )
        other_page = other_authenticated_client.get("/documents")
        assert other_page.status_code == 200
        assert [item["id"] for item in other_page.json()["items"]] == [str(other_document_id)]
        assert other_page.json()["has_more"] is False
    finally:
        with Session(integration_database_engine) as session:
            session.execute(
                delete(Document).where(Document.id.in_([*document_ids, other_document_id]))
            )
            session.commit()

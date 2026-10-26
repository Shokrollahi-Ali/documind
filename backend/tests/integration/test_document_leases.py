import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.documents.leases import (
    claim_document_processing,
    fail_document_processing,
    renew_document_processing_lease,
)
from documind.models.document import Document, DocumentStatus

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("lease_expired", [False, True], ids=["active", "expired"])
def test_reclaim_requires_expired_lease(
    lease_expired: bool,
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    response = authenticated_client.post(
        "/documents",
        files={"file": ("lease-test.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document_id = UUID(response.json()["id"])

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        owner_id = document.owner_id

    async def attempt_claims() -> UUID:
        engine = create_database_engine(integration_settings)
        try:
            session_factory = create_session_factory(engine)

            async with session_factory() as session:
                attempt_id = await claim_document_processing(
                    database_session=session,
                    document_id=document_id,
                    owner_id=owner_id,
                    lease_seconds=300,
                )
                assert attempt_id is not None

            if lease_expired:
                async with session_factory() as session:
                    async with session.begin():
                        await session.execute(
                            update(Document)
                            .where(Document.id == document_id)
                            .values(
                                processing_lease_expires_at=(
                                    func.clock_timestamp() - timedelta(seconds=1)
                                )
                            )
                        )

            async with session_factory() as session:
                second_attempt_id = await claim_document_processing(
                    database_session=session,
                    document_id=document_id,
                    owner_id=owner_id,
                    lease_seconds=300,
                )

            if lease_expired:
                assert second_attempt_id is not None
                assert second_attempt_id != attempt_id
                return second_attempt_id

            assert second_attempt_id is None
            return attempt_id
        finally:
            await engine.dispose()

    attempt_id = asyncio.run(attempt_claims())

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.PROCESSING
        assert document.processing_attempt_id == attempt_id
        assert document.processing_lease_expires_at is not None

        database_time = session.scalar(select(func.clock_timestamp()))
        assert database_time is not None
        assert document.processing_lease_expires_at > database_time


def test_concurrent_claims_grant_only_one_attempt(
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    response = authenticated_client.post(
        "/documents",
        files={"file": ("concurrent-claims.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document_id = UUID(response.json()["id"])

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        owner_id = document.owner_id

    async def claim_concurrently() -> list[UUID | None]:
        engine = create_database_engine(integration_settings)
        try:
            session_factory = create_session_factory(engine)

            async def claim_once() -> UUID | None:
                async with session_factory() as session:
                    return await claim_document_processing(
                        database_session=session,
                        document_id=document_id,
                        owner_id=owner_id,
                        lease_seconds=300,
                    )

            results = await asyncio.wait_for(
                asyncio.gather(claim_once(), claim_once()),
                timeout=5,
            )
            return list(results)
        finally:
            await engine.dispose()

    attempts = asyncio.run(claim_concurrently())
    claimed_attempts = [attempt_id for attempt_id in attempts if attempt_id is not None]
    assert len(claimed_attempts) == 1

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.PROCESSING
        assert document.processing_attempt_id == claimed_attempts[0]


def test_renewal_extends_current_attempt(
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    response = authenticated_client.post(
        "/documents",
        files={"file": ("renewal-test.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document_id = UUID(response.json()["id"])

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        owner_id = document.owner_id

    async def claim_and_renew() -> UUID:
        engine = create_database_engine(integration_settings)
        try:
            session_factory = create_session_factory(engine)

            async with session_factory() as session:
                attempt_id = await claim_document_processing(
                    session, document_id, owner_id, lease_seconds=300
                )
                assert attempt_id is not None

            async with session_factory() as session:
                previous_expiry = await session.scalar(
                    select(Document.processing_lease_expires_at).where(Document.id == document_id)
                )
                assert previous_expiry is not None

            async with session_factory() as session:
                renewed = await renew_document_processing_lease(
                    session, document_id, owner_id, attempt_id, lease_seconds=600
                )
                assert renewed is True

            async with session_factory() as session:
                current_expiry = await session.scalar(
                    select(Document.processing_lease_expires_at).where(Document.id == document_id)
                )
                assert current_expiry is not None
                assert current_expiry > previous_expiry

            return attempt_id
        finally:
            await engine.dispose()

    attempt_id = asyncio.run(claim_and_renew())

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.PROCESSING
        assert document.processing_attempt_id == attempt_id


@pytest.mark.parametrize("operation", ["renew", "fail"])
@pytest.mark.parametrize("attempt_replaced", [False, True], ids=["expired", "replaced"])
def test_stale_attempt_cannot_change_lease(
    operation: str,
    attempt_replaced: bool,
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    response = authenticated_client.post(
        "/documents",
        files={"file": ("stale-attempt.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document_id = UUID(response.json()["id"])
    original_attempt_id = uuid4()
    stored_attempt_id = uuid4() if attempt_replaced else original_attempt_id

    with Session(integration_database_engine) as session:
        with session.begin():
            document = session.get(Document, document_id)
            assert document is not None
            owner_id = document.owner_id

            database_time = session.scalar(select(func.clock_timestamp()))
            assert database_time is not None
            remaining_seconds = 300 if attempt_replaced else -1
            original_expiry = database_time + timedelta(seconds=remaining_seconds)

            document.status = DocumentStatus.PROCESSING
            document.processing_attempt_id = stored_attempt_id
            document.processing_lease_expires_at = original_expiry

    async def attempt_operation() -> bool:
        engine = create_database_engine(integration_settings)
        try:
            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                if operation == "fail":
                    return await fail_document_processing(
                        database_session=session,
                        document_id=document_id,
                        owner_id=owner_id,
                        attempt_id=original_attempt_id,
                    )

                return await renew_document_processing_lease(
                    database_session=session,
                    document_id=document_id,
                    owner_id=owner_id,
                    attempt_id=original_attempt_id,
                    lease_seconds=600,
                )
        finally:
            await engine.dispose()

    assert asyncio.run(attempt_operation()) is False

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.PROCESSING
        assert document.processing_attempt_id == stored_attempt_id
        assert document.processing_lease_expires_at == original_expiry


def test_current_attempt_can_fail_and_release_lease(
    authenticated_client: TestClient,
    integration_database_engine: Engine,
    integration_settings: Settings,
    pdf_content: bytes,
) -> None:
    response = authenticated_client.post(
        "/documents",
        files={"file": ("failed-processing.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document_id = UUID(response.json()["id"])

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        owner_id = document.owner_id

    async def claim_and_fail() -> None:
        engine = create_database_engine(integration_settings)
        try:
            session_factory = create_session_factory(engine)

            async with session_factory() as session:
                attempt_id = await claim_document_processing(
                    session, document_id, owner_id, lease_seconds=300
                )
                assert attempt_id is not None

            async with session_factory() as session:
                failed = await fail_document_processing(
                    database_session=session,
                    document_id=document_id,
                    owner_id=owner_id,
                    attempt_id=attempt_id,
                )
                assert failed is True
        finally:
            await engine.dispose()

    asyncio.run(claim_and_fail())

    with Session(integration_database_engine) as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.status == DocumentStatus.FAILED
        assert document.processing_attempt_id is None
        assert document.processing_lease_expires_at is None

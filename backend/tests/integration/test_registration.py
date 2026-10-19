import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from documind.auth.passwords import verify_password
from documind.auth.registration import EmailAlreadyRegisteredError, register_user
from documind.core.config import Settings
from documind.db.session import create_database_engine, create_session_factory
from documind.models.user import User
from documind.schemas.auth import RegisterRequest

pytestmark = pytest.mark.integration


def test_registration_persists_user_and_rejects_duplicate_email(
    integration_settings: Settings,
) -> None:
    async def run_test() -> None:
        engine = create_database_engine(integration_settings)
        session_factory = create_session_factory(engine)
        email = f"Registration-{uuid4()}@example.com"
        password = "correct-horse-battery-staple"

        try:
            try:
                async with session_factory() as database_session:
                    user = await register_user(
                        database_session=database_session,
                        registration=RegisterRequest(
                            email=email,
                            password=password,
                        ),
                    )
                    user_id = user.id

                    with pytest.raises(EmailAlreadyRegisteredError):
                        await register_user(
                            database_session=database_session,
                            registration=RegisterRequest(
                                email=email.upper(),
                                password="another-valid-test-password",
                            ),
                        )

                async with session_factory() as verification_session:
                    stored_user = await verification_session.get(User, user_id)

                    assert stored_user is not None
                    assert stored_user.email == email.lower()
                    assert verify_password(password, stored_user.password_hash)
                    assert stored_user.created_at is not None
            finally:
                async with session_factory() as cleanup_session:
                    async with cleanup_session.begin():
                        await cleanup_session.execute(
                            delete(User).where(User.email == email.lower())
                        )
        finally:
            await engine.dispose()

    asyncio.run(run_test())


def test_registration_endpoint_persists_user_and_rejects_duplicate(
    integration_client: TestClient, integration_database_engine: Engine
) -> None:
    email = f"Registration-{uuid4()}@example.com"
    password = "correct-horse-battery-staple"

    try:
        response = integration_client.post(
            "/auth/register", json={"email": email, "password": password}
        )

        assert response.status_code == 201
        body = response.json()
        assert set(body) == {"id", "email", "created_at"}
        assert body["email"] == email.lower()
        user_id = UUID(body["id"])

        duplicate_response = integration_client.post(
            "/auth/register",
            json={"email": email.upper(), "password": "another-valid-test-password"},
        )

        assert duplicate_response.status_code == 409
        assert duplicate_response.json() == {"detail": "An account with this email already exists"}

        with Session(integration_database_engine) as database_session:
            users = database_session.scalars(select(User).where(User.email == email.lower())).all()
            assert len(users) == 1
            assert users[0].id == user_id
            assert verify_password(password, users[0].password_hash)
            assert users[0].created_at is not None
    finally:
        with Session(integration_database_engine) as cleanup_session:
            with cleanup_session.begin():
                cleanup_session.execute(delete(User).where(User.email == email.lower()))

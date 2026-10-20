import pytest
from pydantic import ValidationError

from documind.schemas.auth import LoginRequest, RegisterRequest


def test_accepts_valid_registration() -> None:
    request = RegisterRequest(
        email="alice@example.com",
        password="correct-horse-battery-staple",
    )

    assert request.email == "alice@example.com"
    assert request.password.get_secret_value() == "correct-horse-battery-staple"


def test_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError, match="email"):
        RegisterRequest(
            email="not-an-email",
            password="correct-horse-battery-staple",
        )


@pytest.mark.parametrize("password_length", [14, 129])
def test_rejects_password_outside_length_limits(password_length: int) -> None:
    with pytest.raises(ValidationError, match="password"):
        RegisterRequest(
            email="alice@example.com",
            password="a" * password_length,
        )


@pytest.mark.parametrize("password_length", [15, 128])
def test_accepts_password_at_length_limits(password_length: int) -> None:
    request = RegisterRequest(
        email="alice@example.com",
        password="a" * password_length,
    )

    assert len(request.password.get_secret_value()) == password_length


def test_rejects_unexpected_registration_fields() -> None:
    with pytest.raises(ValidationError, match="role"):
        RegisterRequest.model_validate(
            {
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "role": "admin",
            }
        )


@pytest.mark.parametrize("password_length", [1, 14, 128])
def test_login_accepts_existing_passwords_within_its_limits(password_length: int) -> None:
    password = "a" * password_length
    request = LoginRequest(email="alice@example.com", password=password)

    assert request.password.get_secret_value() == password


def test_login_preserves_password_whitespace() -> None:
    password = "  password with spaces  "
    request = LoginRequest(email="alice@example.com", password=password)

    assert request.password.get_secret_value() == password

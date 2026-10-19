import string

from documind.auth.tokens import generate_session_token, hash_session_token

URL_SAFE_CHARACTERS = set(string.ascii_letters + string.digits + "-_")


def test_generated_token_is_long_enough() -> None:
    session_token = generate_session_token()

    assert len(session_token) >= 43


def test_generated_token_is_url_safe() -> None:
    session_token = generate_session_token()

    assert set(session_token) <= URL_SAFE_CHARACTERS


def test_generated_tokens_are_different() -> None:
    assert generate_session_token() != generate_session_token()


def test_token_hash_matches_known_sha256_value() -> None:
    expected_hash = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    assert hash_session_token("abc") == expected_hash

from documind.auth.passwords import hash_password, verify_password


def test_hash_does_not_contain_the_original_password() -> None:
    password_hash = hash_password("correct-horse-battery-staple")

    assert "correct-horse-battery-staple" not in password_hash


def test_hash_uses_argon2id() -> None:
    password_hash = hash_password("correct-horse-battery-staple")

    assert password_hash.startswith("$argon2id$")


def test_hashing_the_same_password_twice_gives_different_hashes() -> None:
    first_hash = hash_password("correct-horse-battery-staple")
    second_hash = hash_password("correct-horse-battery-staple")

    assert first_hash != second_hash


def test_correct_password_is_verified() -> None:
    password_hash = hash_password("correct-horse-battery-staple")

    assert verify_password("correct-horse-battery-staple", password_hash) is True


def test_wrong_password_is_rejected() -> None:
    password_hash = hash_password("correct-horse-battery-staple")

    assert verify_password("wrong-password", password_hash) is False

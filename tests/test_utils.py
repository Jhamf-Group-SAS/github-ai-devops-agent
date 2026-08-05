import pytest

from api.utils import compute_fingerprint, mask_secret, parse_repo_full_name, slugify, truncate


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


def test_slugify_special_chars():
    assert slugify("Hello, World!") == "hello-world"


def test_compute_fingerprint_stable():
    a = compute_fingerprint("same content")
    b = compute_fingerprint("same content")
    assert a == b
    assert len(a) == 64


def test_compute_fingerprint_differs():
    assert compute_fingerprint("a") != compute_fingerprint("b")


def test_mask_secret_long():
    result = mask_secret("supersecretkey", visible=4)
    assert result.endswith("ekey")
    assert "*" in result


def test_mask_secret_short():
    result = mask_secret("abc", visible=4)
    assert result == "***"


def test_parse_repo_full_name_valid():
    owner, repo = parse_repo_full_name("Jhamf-Group-SAS/my-repo")
    assert owner == "Jhamf-Group-SAS"
    assert repo == "my-repo"


def test_parse_repo_full_name_invalid():
    with pytest.raises(ValueError):
        parse_repo_full_name("invalid-no-slash")


def test_truncate_short():
    assert truncate("short", max_length=100) == "short"


def test_truncate_long():
    result = truncate("a" * 300, max_length=200)
    assert len(result) == 200
    assert result.endswith("...")

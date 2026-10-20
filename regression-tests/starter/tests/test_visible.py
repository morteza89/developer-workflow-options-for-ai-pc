from requests.utils import get_auth_from_url, prepend_scheme_if_needed, urldefragauth


def test_add_default_scheme():
    assert prepend_scheme_if_needed("example.org/catalog", "https") == "https://example.org/catalog"


def test_preserve_existing_scheme():
    assert prepend_scheme_if_needed("http://example.org/", "https") == "http://example.org/"


def test_read_plain_credentials():
    assert get_auth_from_url("https://reader:secret@example.org/") == ("reader", "secret")


def test_missing_credentials():
    assert get_auth_from_url("https://example.org/") == ("", "")


def test_remove_fragment_and_userinfo():
    assert urldefragauth("https://reader:secret@example.org/a?b=2#top") == "https://example.org/a?b=2"
import pytest

from requests.utils import get_auth_from_url, prepend_scheme_if_needed, urldefragauth


@pytest.mark.parametrize(
    "url,scheme,expected",
    [
        ("http://example.com/a", "https", "http://example.com/a"),
        ("https://example.com/a", "http", "https://example.com/a"),
        ("example.com/a", "https", "https://example.com/a"),
        ("example.com/a?key=value&other=2", "https", "https://example.com/a?key=value&other=2"),
        ("http://example.com/a?key=value#end", "https", "http://example.com/a?key=value#end"),
        ("example.com:8443/a", "https", "https://example.com:8443/a"),
        ("http://example.com:8080/a", "https", "http://example.com:8080/a"),
        ("//reader:secret@example.com/a", "https", "https://reader:secret@example.com/a"),
        ("//reader:secret@example.com:8443/a?x=1#end", "https", "https://reader:secret@example.com:8443/a?x=1#end"),
        ("//example.com/a", "https", "https://example.com/a"),
    ],
)
def test_prepend_scheme(url, scheme, expected):
    assert prepend_scheme_if_needed(url, scheme) == expected


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://reader:secret@example.com", ("reader", "secret")),
        ("https://read%40er:p%3Ass%20word@example.com", ("read@er", "p:ss word")),
        ("https://a%2Bb:c%2Fd@example.com", ("a+b", "c/d")),
        ("https://example.com", ("", "")),
        ("https://reader@example.com", ("", "")),
        ("https://reader:@example.com", ("reader", "")),
        ("https://:secret@example.com", ("", "secret")),
        ("https://:@example.com", ("", "")),
    ],
)
def test_extract_auth(url, expected):
    assert get_auth_from_url(url) == expected


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com/a#end", "https://example.com/a"),
        ("https://reader:secret@example.com/a", "https://example.com/a"),
        ("https://reader:secret@example.com:8443/a;param?x=1#end", "https://example.com:8443/a;param?x=1"),
        ("https://example.com/a?x=1", "https://example.com/a?x=1"),
        ("https://reader:p@ss@example.com/a#end", "https://example.com/a"),
        ("http://example.com/", "http://example.com/"),
        ("//reader:secret@example.com/a#end", "//example.com/a"),
    ],
)
def test_cleanup(url, expected):
    assert urldefragauth(url) == expected
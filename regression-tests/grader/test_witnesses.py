from pathlib import Path

import requests
from requests import utils


def test_import_contract():
    assert requests.__version__ == "2.31.0"
    assert Path(utils.__file__).resolve().parent == Path(requests.__file__).resolve().parent
    assert Path(utils.__file__).resolve().parent.parent == Path.cwd().resolve()
    assert utils.prepend_scheme_if_needed.__module__ == "requests.utils"
    assert utils.get_auth_from_url.__module__ == "requests.utils"
    assert utils.urldefragauth.__module__ == "requests.utils"


def test_overwrite_existing_scheme():
    assert utils.prepend_scheme_if_needed("ftp://archive.invalid/pub", "https") == "ftp://archive.invalid/pub"


def test_lose_query():
    assert utils.prepend_scheme_if_needed("search.invalid/find?q=two%20words&n=3", "http") == "http://search.invalid/find?q=two%20words&n=3"


def test_drop_port():
    assert utils.prepend_scheme_if_needed("service.invalid:9123/status", "http") == "http://service.invalid:9123/status"


def test_lose_credentials_adding_scheme():
    assert utils.prepend_scheme_if_needed("//alice:pw@service.invalid/status", "http") == "http://alice:pw@service.invalid/status"


def test_fail_percent_decode_credentials():
    assert utils.get_auth_from_url("http://%61lice:p%40ss%2Fword@service.invalid/") == ("alice", "p@ss/word")


def test_wrong_missing_credential_value():
    assert utils.get_auth_from_url("http://service.invalid/status") == ("", "")
    assert utils.get_auth_from_url("http://alice@service.invalid/status") == ("", "")


def test_retain_fragment():
    assert utils.urldefragauth("http://service.invalid:9123/status?view=all#private") == "http://service.invalid:9123/status?view=all"


def test_retain_auth_cleanup():
    assert utils.urldefragauth("http://alice:pw@service.invalid:9123/status?view=all") == "http://service.invalid:9123/status?view=all"
# Requests URL Regression Tests

Requests 2.31.0 at commit `147c8511ddbfa5e8f71bbf5c18ede0c4ceb3bba4` is already correct. Write a regression suite for `prepend_scheme_if_needed`, `get_auth_from_url`, and `urldefragauth` in `requests.utils`. Only `tests/test_generated.py` may change; it starts empty. Do not repair or copy production code.

## Behavior and Import Contract

Import the real functions from `requests.utils` (direct imports or module-qualified calls). Exercise them with concrete inputs and ordinary Python `assert` statements on observable return values. Use literal expected results, not another call to the implementation as the oracle. Do not stub, monkeypatch, wrap, replace, reload, or redirect Requests functions or imports. Do not inspect evaluator paths, fault names, environment state, or source to decide expected results. Do not use skips, xfail, pytest.fail, artificial exceptions, or collection errors as regression detection.

- `prepend_scheme_if_needed(url, new_scheme)` adds a scheme only if missing. Preserve an existing scheme, query, explicit port, credentials, path, and fragment. For example, `example.org/a` with `https` becomes `https://example.org/a`. Use `//user:password@example.org/path` for scheme-less credentials: without the leading `//`, `user:` is parsed as a scheme. Test both already-schemed and scheme-less URLs, with credentials, ports, and queries.
- `get_auth_from_url(url)` returns a two-string tuple. Percent-decode both username and password, including encoded delimiters and spaces. When either credential is absent, Requests returns `("", "")`; empty strings are not `None`. A URL with username but no password also returns `("", "")`. An explicitly empty password is valid and preserves the username.
- `urldefragauth(url)` removes both the fragment and user information, while retaining scheme, host, explicit port, path, parameters, and query. User information ends at the last `@`. URLs without credentials or fragments are preserved.

Use deterministic offline inputs. No HTTP requests are necessary. Include complementary ordinary cases so tests reject broken behavior without rejecting this correct snapshot. Independent evaluation runs your generated file against clean source and eight isolated behavior-changing faults. Each fault must cause an ordinary assertion failure in your suite; errors, skips, and xfail do not count. Visible tests are examples, not your submission.

Run `python -m pytest tests/test_visible.py tests/test_generated.py -q -p no:cacheprovider --import-mode=importlib --noconftest`. Submit within the common 720-second work budget.
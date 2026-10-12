# Security Repair: PyJWT CVE-2022-29217

PyJWT 2.3.0 at the pinned starting revision is vulnerable to key confusion when an application permits both HMAC and asymmetric JWT algorithms. An attacker can sign an HS256 token with public asymmetric key bytes; a verifier that uses the same public key and accepts HS256 can then treat the forged token as valid.

Repair the key handling without disabling legitimate signing or verification. Retain the published key-format and exception behavior, add focused regression tests, run the available checks, and submit a source patch.

## Scope

Editable files: `jwt/algorithms.py`, `jwt/utils.py`, and `tests/test_generated.py`. Do not modify other files, dependencies, test configuration, or the verifier. The source snapshot is PyJWT commit `24b29adfebcb4f057a3cef5aaf35653bc0c1c8cc`; the corresponding upstream repair is commit `9c528670c455b8d948aff95ed50e22940d1ad3fc`.

## Required behavior

- Reject asymmetric PEM and OpenSSH key material when used as an HMAC secret, including Ed25519 and ECDSA public-key encodings that the vulnerable implementation accepts.
- Reject the forged HS256 token demonstrated by `python reproducer.py` and the visible test. Raising `jwt.InvalidKeyError` while preparing the HMAC key is the intended rejection.
- Preserve normal HS256 use with an ordinary symmetric secret.
- Preserve valid RSA, ECDSA, and EdDSA signing and verification.
- Match the upstream exception-contract change: invalid key objects passed to the EdDSA preparation path raise `jwt.InvalidKeyError`, not the former `TypeError`.
- Add a regression test that passes on your repair and fails on the unmodified vulnerable source. The independent verifier checks both outcomes.

Do not reject every key, disable signature verification, change the accepted-algorithm contract, or hardcode a response to the visible fixture. The protected verifier also checks additional key formats and legitimate operations.

## Environment

The container is prepared and offline. Run `python -m pytest -q -p no:cacheprovider` and `python reproducer.py`. Do not install packages or access the network. You have 240 seconds for model calls, edits, visible tests, and repairs. Keep each action short and complete. At the deadline, captured files are evaluated as-is; no protected feedback is returned for another repair round.

# Maintainer Notes

This is a sanitized source snapshot of PyJWT 2.3.0. The issue is CVE-2022-29217 / GHSA-ffqj-6fqr-9h24. The affected behavior is in the HMAC and OKP key preparation paths in `jwt/algorithms.py`; key-format recognition belongs in `jwt/utils.py`.

The vulnerable branch rejects several historically recognized PEM labels and `ssh-rsa`, but does not consistently recognize other PEM and OpenSSH asymmetric formats. Ed25519 OpenSSH public keys are one concrete bypass. The token header selects HS256, and the application accidentally accepts it while using the asymmetric public key as the verification key.

Run the local reproducer and inspect the key preparation code before changing it. Preserve algorithm-specific behavior: a symmetric HMAC secret remains valid, and supported asymmetric private/public key pairs must continue to work. The reference patch also deliberately normalizes invalid EdDSA key failures to `InvalidKeyError`; that exception change is part of this backport contract.

All dependencies are installed from the pinned, hash-locked container requirements. The task has no network access. `tests/test_visible.py` gives the basic reproducer; your generated tests should capture the rejection and must fail against this vulnerable starting snapshot.

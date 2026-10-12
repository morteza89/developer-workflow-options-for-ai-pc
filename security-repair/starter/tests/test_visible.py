import base64
import hashlib
import hmac
import json

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def _segment(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def _forged_hs256(public_key):
    header = _segment(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _segment(json.dumps({"sub": "visible-test"}, separators=(",", ":")).encode())
    message = header + b"." + payload
    signature = hmac.new(public_key, message, hashlib.sha256).digest()
    return message.decode() + "." + _segment(signature).decode()


def test_ed25519_public_key_cannot_be_used_as_hmac_secret():
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    )
    token = _forged_hs256(public_key)
    with pytest.raises(jwt.InvalidKeyError):
        jwt.decode(token, public_key, algorithms=jwt.algorithms.get_default_algorithms())


def test_ordinary_hmac_secret_still_works():
    claims = {"sub": "normal-hmac"}
    token = jwt.encode(claims, "ordinary-symmetric-secret", algorithm="HS256")
    assert jwt.decode(token, "ordinary-symmetric-secret", algorithms=["HS256"]) == claims

import base64
import hashlib
import hmac
import json

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519


def _segment(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def _forged_hs256(public_key):
    header = _segment(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _segment(json.dumps({"sub": "generated-regression"}, separators=(",", ":")).encode())
    message = header + b"." + payload
    signature = hmac.new(public_key, message, hashlib.sha256).digest()
    return message.decode() + "." + _segment(signature).decode()


def test_ed25519_openssh_public_key_cannot_verify_hs256():
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    )
    with pytest.raises(jwt.InvalidKeyError):
        jwt.decode(_forged_hs256(public_key), public_key, algorithms=["HS256"])


def test_ecdsa_openssh_public_key_cannot_verify_hs256():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    )
    with pytest.raises(jwt.InvalidKeyError):
        jwt.decode(_forged_hs256(public_key), public_key, algorithms=["HS256"])

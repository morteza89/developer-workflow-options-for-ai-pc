import base64
from datetime import datetime, timedelta
import hashlib
import hmac
import json

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from cryptography.x509.oid import NameOID


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


def test_asymmetric_key_encodings_cannot_be_used_as_hmac_secrets():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "visible-test")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(1)
        .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
        .not_valid_after(datetime.utcnow() + timedelta(days=1))
        .sign(private_key, hashes.SHA256())
        .public_bytes(serialization.Encoding.PEM)
    )
    keys = [
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.PKCS1,
        ),
        private_key.public_key().public_bytes(
            serialization.Encoding.OpenSSH,
            serialization.PublicFormat.OpenSSH,
        ),
        certificate,
    ]
    ecdsa_key = ec.generate_private_key(ec.SECP256R1())
    keys.append(ecdsa_key.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    ))
    algorithm = jwt.algorithms.get_default_algorithms()["HS256"]
    for key in keys:
        with pytest.raises(jwt.InvalidKeyError):
            algorithm.prepare_key(key)


def test_ordinary_hmac_secret_still_works():
    claims = {"sub": "normal-hmac"}
    token = jwt.encode(claims, "ordinary-symmetric-secret", algorithm="HS256")
    assert jwt.decode(token, "ordinary-symmetric-secret", algorithms=["HS256"]) == claims

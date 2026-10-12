import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from cryptography.x509.oid import NameOID


def _segment(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def _forged_hs256(public_key):
    header = _segment(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _segment(json.dumps({"sub": "security-test"}, separators=(",", ":")).encode())
    message = header + b"." + payload
    signature = hmac.new(public_key, message, hashlib.sha256).digest()
    return message.decode() + "." + _segment(signature).decode()


def _pem(key, encoding, fmt):
    return key.public_bytes(encoding, fmt)


def _certificate(public_key, signer):
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "local-test")])
    now = datetime.now(timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(signer, hashes.SHA256())
        .public_bytes(serialization.Encoding.PEM)
    )


@pytest.mark.parametrize("key_format", ["ed25519-ssh", "ecdsa-ssh"])
def test_public_ssh_key_cannot_be_used_to_forge_hmac_token(key_format):
    if key_format == "ed25519-ssh":
        private = ed25519.Ed25519PrivateKey.generate()
    else:
        private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    )
    token = _forged_hs256(public)
    with pytest.raises(jwt.InvalidKeyError):
        jwt.decode(token, public, algorithms=jwt.algorithms.get_default_algorithms())


def test_asymmetric_pem_public_private_and_certificate_are_not_hmac_secrets():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    formats = [
        private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        _certificate(private.public_key(), private),
    ]
    algorithm = jwt.algorithms.get_default_algorithms()["HS256"]
    for key in formats:
        with pytest.raises(jwt.InvalidKeyError):
            algorithm.prepare_key(key)


def test_ssh_rsa_and_legacy_pem_rsa_public_formats_are_rejected():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ssh = private.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    )
    pkcs1 = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.PKCS1,
    )
    algorithm = jwt.algorithms.get_default_algorithms()["HS256"]
    for key in (ssh, pkcs1):
        with pytest.raises(jwt.InvalidKeyError):
            algorithm.prepare_key(key)


def test_hmac_rejection_is_specific_to_asymmetric_key_material():
    algorithm = jwt.algorithms.get_default_algorithms()["HS256"]
    assert algorithm.prepare_key("ordinary symmetric secret") == b"ordinary symmetric secret"
    token = jwt.encode({"scope": "read"}, "ordinary symmetric secret", algorithm="HS256")
    assert jwt.decode(token, "ordinary symmetric secret", algorithms=["HS256"]) == {"scope": "read"}

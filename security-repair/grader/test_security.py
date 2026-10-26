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

_OPENSSH_PUBLIC = (serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
_SPKI = (serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
# Real 1024-bit DSA public key in OpenSSH form; DSA generation is deprecated in cryptography 42 so it is embedded.
_SSH_DSS_PUBLIC = (
    b"ssh-dss AAAAB3NzaC1kc3MAAACBALRXqNYBunSdHd3Bd7T5E0rcd+LDS3SJl/atAmZbmHrrKe1OOwrWVvr38uuA1jgZgZ0cRJdfnqCde5dEyno9Q6B731dSIlXjQ+Fh9MscsOFzbJaHG1fe4udp3m0pgjJLGhQhbZ3GWdY6rwRQkq/szZqD25C4PTzI7+JQmbqmO0ZlAAAAFQDpLOrNrduMfu+lnQpFWx3WEQICJwAAAIAyCx8oaUYbknFK6Sl0X6zNwn69YWRxawoXa6jMfj52T/CA4l66nIIqVHwt/otd6y0GZvqj3r7DuQAIJD26SVqizh6wa+ObobtbhVZVsWSqYug8SoQxISYQ41STo7C7uODAYgWh6ppeguKZvtUlTwgfeC6tr3VoWruFJbd6IEPHDwAAAIBdryWmvbZQ6+RJTvXxDOlPQ0QIRf8mW4yAJE16KRT1nP1NwGdQDmx39ZwIiKajKW0IPFVWrZiVcnb+G3OL5tbG9iqrRbL+ePCcoq+dfIJrurIfOV6F7SILJhz7UW2l5j/ecmhJCl8kWte1hbM7TMGZdtksaVOkTeu3VSyXepAHBA=="
)


def _segment(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def _private_pem(private_key, fmt=serialization.PrivateFormat.PKCS8):
    return private_key.private_bytes(serialization.Encoding.PEM, fmt, serialization.NoEncryption())


def _hmac_algorithm():
    return jwt.algorithms.get_default_algorithms()["HS256"]


def _assert_not_hmac_secret(key):
    with pytest.raises(jwt.InvalidKeyError):
        _hmac_algorithm().prepare_key(key)
    with pytest.raises(jwt.InvalidKeyError):
        jwt.decode(_forged_hs256(key), key, algorithms=jwt.algorithms.get_default_algorithms())


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


def test_pem_material_embedded_after_a_prefix_is_not_an_hmac_secret():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    spki = private.public_key().public_bytes(*_SPKI)
    certificate = _certificate(private.public_key(), private)
    _assert_not_hmac_secret(b"\n" + spki)
    _assert_not_hmac_secret(b"\r\n" + spki)
    _assert_not_hmac_secret(b"Certificate:\n    Data:\n        Version: 3 (0x2)\n" + certificate)
    _assert_not_hmac_secret(b"# issued key\n" + spki + b"\n# trailing comment\n")


def test_traditional_and_openssh_private_pem_formats_are_not_hmac_secrets():
    rsa_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ec_private = ec.generate_private_key(ec.SECP256R1())
    ed_private = ed25519.Ed25519PrivateKey.generate()
    rsa_traditional = _private_pem(rsa_private, serialization.PrivateFormat.TraditionalOpenSSL)
    ec_traditional = _private_pem(ec_private, serialization.PrivateFormat.TraditionalOpenSSL)
    openssh_private = _private_pem(ed_private, serialization.PrivateFormat.OpenSSH)
    assert rsa_traditional.startswith(b"-----BEGIN RSA PRIVATE KEY-----")
    assert ec_traditional.startswith(b"-----BEGIN EC PRIVATE KEY-----")
    assert openssh_private.startswith(b"-----BEGIN OPENSSH PRIVATE KEY-----")
    for key in (rsa_traditional, ec_traditional, openssh_private):
        _assert_not_hmac_secret(key)


def test_every_openssh_public_key_type_is_rejected_as_hmac_secret():
    keys = [
        _SSH_DSS_PUBLIC,
        ec.generate_private_key(ec.SECP384R1()).public_key().public_bytes(*_OPENSSH_PUBLIC),
        ec.generate_private_key(ec.SECP521R1()).public_key().public_bytes(*_OPENSSH_PUBLIC),
    ]
    assert keys[0].startswith(b"ssh-dss ")
    assert keys[1].startswith(b"ecdsa-sha2-nistp384 ")
    assert keys[2].startswith(b"ecdsa-sha2-nistp521 ")
    for key in keys:
        _assert_not_hmac_secret(key)


def test_openssh_public_key_with_leading_whitespace_or_options_is_not_an_hmac_secret():
    ssh_ed25519 = ed25519.Ed25519PrivateKey.generate().public_key().public_bytes(*_OPENSSH_PUBLIC)
    ssh_rsa = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key().public_bytes(*_OPENSSH_PUBLIC)
    _assert_not_hmac_secret(b" " + ssh_ed25519)
    _assert_not_hmac_secret(b"\t\n" + ssh_ed25519)
    _assert_not_hmac_secret(b"no-pty,no-port-forwarding " + ssh_ed25519)
    _assert_not_hmac_secret(b'command="/bin/true" ' + ssh_rsa)
    _assert_not_hmac_secret(b"ssh-ed25519-cert-v01@openssh.com AAAA")


def test_hmac_signature_mismatch_is_still_rejected():
    token = jwt.encode({"sub": "secret-a"}, "shared-secret-a", algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "shared-secret-b", algorithms=["HS256"])
    header, payload, signature = token.split(".")
    raw = bytearray(base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4)))
    raw[0] ^= 0x01
    tampered = ".".join((header, payload, _segment(bytes(raw)).decode()))
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(tampered, "shared-secret-a", algorithms=["HS256"])
    assert jwt.decode(token, "shared-secret-a", algorithms=["HS256"]) == {"sub": "secret-a"}


def test_asymmetric_signatures_are_rejected_under_the_wrong_public_key():
    claims = {"sub": "asymmetric"}
    rsa_private, other_rsa = (rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2))
    rsa_token = jwt.encode(claims, _private_pem(rsa_private), algorithm="RS256")
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(rsa_token, other_rsa.public_key().public_bytes(*_SPKI), algorithms=["RS256"])
    assert jwt.decode(rsa_token, rsa_private.public_key().public_bytes(*_SPKI), algorithms=["RS256"]) == claims

    ec_private, other_ec = (ec.generate_private_key(ec.SECP256R1()) for _ in range(2))
    ec_token = jwt.encode(claims, ec_private, algorithm="ES256")
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(ec_token, other_ec.public_key(), algorithms=["ES256"])

    ed_private, other_ed = (ed25519.Ed25519PrivateKey.generate() for _ in range(2))
    ed_token = jwt.encode(claims, ed_private, algorithm="EdDSA")
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(ed_token, other_ed.public_key(), algorithms=["EdDSA"])
    assert jwt.decode(ed_token, ed_private.public_key(), algorithms=["EdDSA"]) == claims


def test_eddsa_prepare_key_rejects_rsa_material():
    rsa_public = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    algorithm = jwt.algorithms.OKPAlgorithm()
    with pytest.raises(jwt.InvalidKeyError):
        algorithm.prepare_key(rsa_public.public_bytes(*_OPENSSH_PUBLIC))
    with pytest.raises(jwt.InvalidKeyError):
        algorithm.prepare_key(rsa_public)
    with pytest.raises(jwt.InvalidKeyError):
        algorithm.prepare_key(rsa_public.public_bytes(*_SPKI))
    with pytest.raises(jwt.InvalidKeyError):
        algorithm.prepare_key(ec.generate_private_key(ec.SECP256R1()).public_key())

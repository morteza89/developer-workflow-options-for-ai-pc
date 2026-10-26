import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from jwt.algorithms import OKPAlgorithm


def _pem_private(private_key):
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def test_ed25519_pem_signing_and_openssh_verification_remain_valid():
    private = ed25519.Ed25519PrivateKey.generate()
    private_pem = _pem_private(private)
    public_ssh = private.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    )
    claims = {"sub": "ed25519"}
    token = jwt.encode(claims, private_pem, algorithm="EdDSA")
    assert jwt.decode(token, public_ssh, algorithms=["EdDSA"]) == claims
    assert jwt.decode(jwt.encode(claims, private, algorithm="EdDSA"), private.public_key(), algorithms=["EdDSA"]) == claims


def test_rsa_and_ecdsa_signatures_remain_valid():
    claims = {"sub": "asymmetric"}
    rsa_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rsa_public = rsa_private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    rsa_token = jwt.encode(claims, _pem_private(rsa_private), algorithm="RS256")
    assert jwt.decode(rsa_token, rsa_public, algorithms=["RS256"]) == claims

    ec_private = ec.generate_private_key(ec.SECP256R1())
    ec_public = ec_private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    ec_token = jwt.encode(claims, _pem_private(ec_private), algorithm="ES256")
    assert jwt.decode(ec_token, ec_public, algorithms=["ES256"]) == claims


def test_invalid_eddsa_key_uses_invalid_key_error_contract():
    with pytest.raises(jwt.InvalidKeyError):
        OKPAlgorithm().prepare_key(None)
    with pytest.raises(jwt.InvalidKeyError):
        OKPAlgorithm().prepare_key(b"not a serialized key")


@pytest.mark.parametrize(
    ("algorithm", "curve"),
    [("ES256", ec.SECP256R1), ("ES384", ec.SECP384R1), ("ES512", ec.SECP521R1)],
)
def test_ecdsa_openssh_public_keys_still_verify(algorithm, curve):
    claims = {"sub": algorithm}
    private = ec.generate_private_key(curve())
    public_ssh = private.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    )
    assert public_ssh.startswith(b"ecdsa-sha2-nistp")
    token = jwt.encode(claims, _pem_private(private), algorithm=algorithm)
    assert jwt.decode(token, public_ssh, algorithms=[algorithm]) == claims


def test_rsa_openssh_public_key_still_verifies():
    claims = {"sub": "ssh-rsa"}
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_ssh = private.public_key().public_bytes(
        serialization.Encoding.OpenSSH,
        serialization.PublicFormat.OpenSSH,
    )
    token = jwt.encode(claims, _pem_private(private), algorithm="RS256")
    assert jwt.decode(token, public_ssh, algorithms=["RS256"]) == claims

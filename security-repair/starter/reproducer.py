import base64
import hashlib
import hmac
import json

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key().public_bytes(
    serialization.Encoding.OpenSSH,
    serialization.PublicFormat.OpenSSH,
)

def encode_segment(value):
    encoded = base64.urlsafe_b64encode(value).rstrip(b"=")
    return encoded

header = encode_segment(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
payload = encode_segment(json.dumps({"sub": "local-demo"}, separators=(",", ":")).encode())
message = header + b"." + payload
signature = hmac.new(public_key, message, hashlib.sha256).digest()
token = message.decode() + "." + encode_segment(signature).decode()

try:
    claims = jwt.decode(token, public_key, algorithms=jwt.algorithms.get_default_algorithms())
except jwt.InvalidKeyError as error:
    print(f"Rejected with InvalidKeyError: {error}")
else:
    print(f"VULNERABLE: forged HS256 token accepted with claims {claims!r}")

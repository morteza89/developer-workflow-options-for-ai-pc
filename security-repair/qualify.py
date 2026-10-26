"""Qualify vulnerable, fixed, and deliberately wrong Security Repair snapshots."""

import argparse
import json
import re
import shutil
import sys
import uuid
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent / "dependency-migration"
sys.path.insert(0, str(ENGINE_ROOT))

import bench

ROOT = Path(__file__).resolve().parent
bench.configure_package(ROOT)


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def check(image):
    image_id = bench.image_id(image)
    policy = bench.load(ROOT / "policy.json")
    artifacts = ROOT / "artifacts" / ("qualification-" + uuid.uuid4().hex[:12])
    artifacts.mkdir(parents=True)
    results = {}

    def evaluate(name, source):
        output = artifacts / name
        output.mkdir()
        result = bench.verify(source, output, image, policy)
        save(output / "result.json", result)
        if result.get("cleanup_errors"):
            raise RuntimeError(f"Verifier cleanup failed during {name}")
        return result

    vulnerable_source = artifacts / "mutants" / "starting-vulnerable" / "source"
    shutil.copytree(ROOT / "starter", vulnerable_source)
    shutil.copyfile(ROOT / "reference/tests/test_generated.py", vulnerable_source / "tests/test_generated.py")
    vulnerable = evaluate("starting-vulnerable", vulnerable_source)
    if vulnerable["checks"].get("contract") or vulnerable["checks"].get("generated") or not vulnerable["checks"].get("negative_control") or not any("public_ssh_key" in test for test in vulnerable.get("failed_tests", [])):
        raise RuntimeError("The pinned starting source did not reproduce the protected exploit failure")
    results["starting-vulnerable"] = {"expected": "reject", "observed": vulnerable["category"], "checks": vulnerable["checks"]}

    reference = evaluate("upstream-reference", ROOT / "reference")
    if not reference["accepted"]:
        raise RuntimeError("The upstream reference did not pass the protected and generated-test checks")
    results["upstream-reference"] = {"expected": "accept", "observed": "accepted", "checks": reference["checks"]}

    mutants = {
        "restore-vulnerable-source": lambda path: [
            shutil.copyfile(ROOT / "starter/jwt/algorithms.py", path / "jwt/algorithms.py"),
            shutil.copyfile(ROOT / "starter/jwt/utils.py", path / "jwt/utils.py"),
        ],
        "allow-openssh-as-hmac": lambda path: mutate_once(
            path / "jwt/algorithms.py",
            "if is_pem_format(key) or is_ssh_key(key):",
            "if is_pem_format(key):",
        ),
        "reject-all-hmac": lambda path: mutate_once(
            path / "jwt/algorithms.py",
            "if is_pem_format(key) or is_ssh_key(key):",
            "if True:",
        ),
        "restore-eddsa-typeerror": lambda path: mutate_once(
            path / "jwt/algorithms.py",
            "raise InvalidKeyError(\n                    \"Expecting a EllipticCurvePrivateKey/EllipticCurvePublicKey. Wrong key provided for EdDSA algorithms\"\n                )",
            "raise TypeError(\n                    \"Expecting a EllipticCurvePrivateKey/EllipticCurvePublicKey. Wrong key provided for EdDSA algorithms\"\n                )",
        ),
        # Every Algorithm.verify returns True: key confusion is "fixed" but no signature is ever checked.
        "disable-signature-verification": lambda path: mutate_every(
            path / "jwt/algorithms.py",
            r"(\n(\s+)def verify\(self, msg, key, sig\):\n)",
            r"\1\2    return True\n",
            minimum=6,
        ),
        # Prefix-only recognisers accept PEM after a newline/text prefix and OpenSSH lines with options.
        "prefix-only-key-detection": lambda path: [
            mutate_once(
                path / "jwt/utils.py",
                "def is_pem_format(key: bytes) -> bool:\n    return bool(_PEM_RE.search(key))",
                "def is_pem_format(key: bytes) -> bool:\n    return key.startswith(b\"-----BEGIN\")",
            ),
            mutate_once(
                path / "jwt/utils.py",
                "def is_ssh_key(key: bytes) -> bool:\n",
                "def is_ssh_key(key: bytes) -> bool:\n    return key.startswith(b\"ssh-\") or key.startswith(b\"ecdsa-sha2-\")\n",
            ),
        ],
        # Starter-style substring list covering only the visible formats (no traditional/OpenSSH private PEM, ssh-dss, nistp384/521).
        "narrowed-key-detection": lambda path: [
            shutil.copyfile(ROOT / "starter/jwt/utils.py", path / "jwt/utils.py"),
            mutate_once(path / "jwt/algorithms.py", "    is_pem_format,\n    is_ssh_key,\n", ""),
            mutate_once(
                path / "jwt/algorithms.py",
                "        if is_pem_format(key) or is_ssh_key(key):",
                "        invalid_strings = [b\"-----BEGIN PUBLIC KEY-----\", b\"-----BEGIN CERTIFICATE-----\", b\"-----BEGIN RSA PUBLIC KEY-----\", b\"-----BEGIN PRIVATE KEY-----\", b\"ssh-rsa\", b\"ssh-ed25519\", b\"ecdsa-sha2-nistp256\"]\n        if any(s in key for s in invalid_strings):",
            ),
        ],
        # ECAlgorithm.prepare_key no longer loads OpenSSH public keys (ecdsa-sha2-* verification breaks).
        "drop-ecdsa-openssh-loading": lambda path: mutate_once(
            path / "jwt/algorithms.py",
            "                if key.startswith(b\"ecdsa-sha2-\"):\n                    key = load_ssh_public_key(key)\n                else:\n                    key = load_pem_public_key(key)",
            "                key = load_pem_public_key(key)",
        ),
        # OKPAlgorithm.prepare_key keeps the InvalidKeyError contract but accepts any loaded key object (ssh-rsa, RSA public key).
        "eddsa-accepts-wrong-key-family": lambda path: mutate_once(
            path / "jwt/algorithms.py",
            "            if not isinstance(\n                key,\n                (Ed25519PrivateKey, Ed25519PublicKey, Ed448PrivateKey, Ed448PublicKey),\n            ):",
            "            if key is None or isinstance(key, (bytes, str)):",
        ),
    }
    mutant_root = artifacts / "mutants"
    mutant_root.mkdir(exist_ok=True)
    for name, mutate in mutants.items():
        source = mutant_root / name / "source"
        shutil.copytree(ROOT / "reference", source)
        mutate(source)
        result = evaluate(name, source)
        if result["accepted"]:
            raise RuntimeError(f"The verifier accepted deliberately incorrect control {name}")
        results[name] = {"expected": "reject", "observed": result["category"], "checks": result["checks"]}

    evidence = {
        "image": image_id,
        "starting_commit": bench.WORKFLOW["starting_commit"],
        "reference_commit": bench.WORKFLOW["reference_commit"],
        "results": results,
    }
    save(artifacts / "qualification.json", evidence)
    print(json.dumps(evidence, indent=2))
    print(f"Evidence: {artifacts}")
    return 0


def mutate_once(path, before, after):
    source = path.read_text(encoding="utf-8")
    if source.count(before) != 1:
        raise RuntimeError(f"Expected exactly one mutation target in {path.name}")
    path.write_text(source.replace(before, after), encoding="utf-8")


def mutate_every(path, pattern, replacement, minimum):
    source, count = re.subn(pattern, replacement, path.read_text(encoding="utf-8"))
    if count < minimum:
        raise RuntimeError(f"Expected at least {minimum} mutation targets in {path.name}, found {count}")
    path.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check"])
    parser.add_argument("--image", default="pyjwt-security:0.1")
    args = parser.parse_args()
    try:
        sys.exit(check(args.image))
    except (OSError, RuntimeError, ValueError, bench.subprocess.SubprocessError) as error:
        print(f"Blocked: {error}", file=sys.stderr)
        sys.exit(2)

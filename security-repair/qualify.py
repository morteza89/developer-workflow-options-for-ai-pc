"""Qualify vulnerable, fixed, and deliberately wrong Security Repair snapshots."""

import argparse
import json
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

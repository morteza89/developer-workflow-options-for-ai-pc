"""Trusted author-only qualification; never execute untrusted submissions on the host."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def interpreter(version):
    directory = ROOT / f".venv-{version}"
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def execute(command, cwd=ROOT):
    environment = {key: value for key, value in os.environ.items() if not key.startswith(("EXPENSE_", "PYTEST_", "PYTHONPATH"))}
    environment.update(PYTHONPATH=str(cwd), PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    return subprocess.run([str(part) for part in command], cwd=cwd, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def prepare():
    for version in ("v1", "v2"):
        directory = ROOT / f".venv-{version}"
        if directory.exists():
            if not (directory / "pyvenv.cfg").is_file() or not interpreter(version).is_file():
                raise RuntimeError(f"{directory} is not a usable virtual environment. Move it aside before rerunning prepare; no files were removed.")
            probe = execute([interpreter(version), "-c", "import sys; assert sys.version_info[:2] == (3, 11) and sys.prefix != sys.base_prefix"])
            if probe.returncode:
                raise RuntimeError(f"{directory} must be a working Python 3.11 virtual environment. Move it aside before rerunning prepare; no files were removed.\n{probe.stdout}{probe.stderr}")
            print(f"Reusing {directory.name}.")
            commands = []
        else:
            commands = [["uv", "venv", "--python", "3.11", directory]]
        commands.append(["uv", "pip", "sync", "--python", interpreter(version), "--require-hashes", ROOT / f"requirements-{version}.lock"])
        for command in commands:
            result = execute(command)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
    print("Prepared locked v1 and v2 authoring environments.")


def check(version, source, native=False, report=None):
    tests = [ROOT / "grader/test_contract.py"]
    if native:
        tests.append(ROOT / "grader/test_native.py")
    arguments = [interpreter(version), "-W", "error::pydantic.PydanticDeprecatedSince20", "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider", "--import-mode=importlib"]
    if report is not None:
        arguments.append(f"--junitxml={report}")
    return execute(arguments, source)


def qualify():
    for version in ("v1", "v2"):
        if not interpreter(version).is_file():
            raise SystemExit("Run python qualify.py prepare first.")
    artifacts = ROOT / "artifacts" / f"qualification-{uuid.uuid4().hex[:12]}"
    artifacts.mkdir(parents=True)
    results = {}
    inputs = [path for folder in ("starter", "reference", "grader") for path in (ROOT / folder).rglob("*") if path.is_file() and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts]
    inputs += [ROOT / "qualify.py", ROOT / "requirements-v1.lock", ROOT / "requirements-v2.lock"]
    evidence = {"hashes": {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}, "environments": {}}
    for version in ("v1", "v2"):
        script = "import importlib.metadata as meta,json,sys,platform; print(json.dumps({'python':sys.version,'platform':platform.platform(),'packages':{dist.metadata['Name']:dist.version for dist in meta.distributions()}}))"
        inventory = execute([interpreter(version), "-c", script])
        if inventory.returncode:
            raise RuntimeError(inventory.stderr)
        evidence["environments"][version] = json.loads(inventory.stdout)
        drift_script = "from packaging.requirements import Requirement; import pathlib,importlib.metadata as meta; lines=pathlib.Path('requirements-" + version + ".lock').read_text().splitlines(); requirements=[Requirement(line.rstrip('\\\\ ')) for line in lines if line and not line[0].isspace() and not line.startswith('#')]; assert all(meta.version(req.name) in req.specifier for req in requirements if not req.marker or req.marker.evaluate()), 'dependency drift'"
        drift = execute([interpreter(version), "-c", drift_script])
        if drift.returncode:
            raise RuntimeError("Environment changed; rerun prepare. " + drift.stderr)
    (artifacts / "inputs.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    def record(name, result, expected_pass):
        (artifacts / f"{name}.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
        results[name] = {"exit_code": result.returncode, "expected_pass": expected_pass, "qualified": (result.returncode == 0) == expected_pass}
        print(f"{name}: {'PASS' if results[name]['qualified'] else 'FAIL'} (exit {result.returncode})")

    def record_check(name, version, source, expected_pass, native=False, expected_test=None):
        report = artifacts / f"{name}.xml"
        outcome = check(version, source, native=native, report=report)
        record(name, outcome, expected_pass)
        cases = list(ET.parse(report).getroot().iter("testcase")) if report.exists() else []
        failures = [case.attrib["name"] for case in cases if case.find("failure") is not None]
        results[name].update(test_count=len(cases), failed_tests=failures)
        if expected_test:
            results[name]["qualified"] = outcome.returncode == 1 and any(expected_test in failure for failure in failures) and not any(case.find("error") is not None for case in cases)
        elif not expected_pass:
            results[name]["qualified"] = outcome.returncode == 2 and "PydanticUserError" in outcome.stdout and "root_validator" in outcome.stdout
        return outcome

    record_check("v1-original", "v1", ROOT / "starter", True)
    record_check("v2-unmodified", "v2", ROOT / "starter", False)
    record_check("v2-reference", "v2", ROOT / "reference", True, native=True)
    record("reference-generated-tests", execute([interpreter("v2"), "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], ROOT / "reference"), True)
    with tempfile.TemporaryDirectory(prefix="migration-codemod-") as temporary:
        source = Path(temporary) / "task"
        shutil.copytree(ROOT / "starter", source)
        codemod = execute([interpreter("v2"), "-m", "bump_pydantic", "app"], source)
        record("codemod-execution", codemod, True)
        record_check("codemod-incomplete", "v2", source, False, native=True)
        shutil.copytree(source / "app", artifacts / "codemod-app")
    mutations = {
        "lost-null-presence": ("routes.py", "exclude_unset=True", "exclude_none=True"),
        "required-notes": ("schemas.py", "notes: str | None = None", "notes: str | None"),
        "lost-aliases": ("routes.py", "by_alias=True", "by_alias=False"),
        "lost-merchant-coercion": ("schemas.py", "return str(value) if isinstance(value, int) and not isinstance(value, bool) else value", "return value"),
        "receipt-boundary": ("schemas.py", "self.amount_cents > 10000", "self.amount_cents >= 10000"),
        "receipt-disabled": ("schemas.py", 'self.category == "work"', "False"),
        "lost-settings-prefix": ("settings.py", 'env_prefix="EXPENSE_"', 'env_prefix="WRONG_"'),
        "lost-object-loading": ("schemas.py", "from_attributes=True", "from_attributes=False"),
        "legacy-call": ("routes.py", "expense.model_dump(by_alias=True)", "expense.dict(by_alias=True)"),
            "compatibility-import": ("schemas.py", "from typing import Literal", "from typing import Literal\nfrom pydantic import v1"),
            "bypassed-request-model": ("routes.py", "def create_expense(expense: ExpenseCreate):", "def create_expense(expense: dict):"),
            "hardcoded-object-response": ("routes.py", "return ExpenseRead.model_validate(record).model_dump(by_alias=True)", 'return {"expenseId": 7, "externalId": "seed-7", "merchantCode": "42", "amountCents": 12500, "category": "work", "receipt": "R-7", "notes": None}'),
        "receipt-stripped": ("schemas.py", "and not self.receipt", 'and not (self.receipt or "").strip()'),
        "receipt-discarded": ("routes.py", "return expense.model_dump(by_alias=True)", 'return expense.model_dump(by_alias=True) | {"receipt": None}'),
    }
    expected_tests = {"lost-null-presence": "test_patch_presence", "required-notes": "test_field_names_and_omitted_notes", "lost-aliases": "test_alias_json_values", "lost-merchant-coercion": "test_integer_merchant_codes", "receipt-boundary": "test_receipt_semantics", "receipt-disabled": "test_receipt_semantics", "lost-settings-prefix": "test_startup_settings", "lost-object-loading": "test_object_serialization", "legacy-call": "test_no_legacy_api", "compatibility-import": "test_no_legacy_api", "bypassed-request-model": "test_routes_keep_model_boundaries_and_load_runtime_attributes", "hardcoded-object-response": "test_routes_keep_model_boundaries_and_load_runtime_attributes", "receipt-stripped": "test_receipt_semantics", "receipt-discarded": "test_receipt_semantics"}
    for name, (filename, before, after) in mutations.items():
        with tempfile.TemporaryDirectory(prefix="migration-control-") as temporary:
            source = Path(temporary) / "task"
            shutil.copytree(ROOT / "reference", source)
            path = source / "app" / filename
            original = path.read_text(encoding="utf-8")
            if before not in original:
                raise RuntimeError(f"Mutation {name} no longer applies")
            path.write_text(original.replace(before, after), encoding="utf-8")
            record_check(name, "v2", source, False, native=True, expected_test=expected_tests[name])
    (artifacts / "qualification.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Evidence: {artifacts}")
    return 0 if all(result["qualified"] for result in results.values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "check"])
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    else:
        sys.exit(qualify())
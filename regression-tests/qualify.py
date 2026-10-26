"""Qualify Requests test authoring; local evidence is not isolated qualification."""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
ENGINE_ROOT = ROOT.parent / "dependency-migration"
sys.path.insert(0, str(ENGINE_ROOT))

import bench as engine

engine.configure_package(ROOT)
GENERATED = "tests/test_generated.py"


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def mutate_once(source, fault):
    path = source / fault["path"]
    text = path.read_text(encoding="utf-8")
    if text.count(fault["before"]) != 1 or fault["before"] == fault["after"]:
        raise RuntimeError(f"Non-unique or inert fault: {fault['name']}")
    path.write_text(text.replace(fault["before"], fault["after"], 1), encoding="utf-8")


def snapshot(destination, suite=None):
    shutil.copytree(ROOT / "starter", destination)
    if suite is not None:
        (destination / GENERATED).write_text(suite, encoding="utf-8")
    return destination


def behavioral_names(suite):
    return engine.behavioral_test_names(ast.parse(suite))


def validate_package():
    manifest = engine.WORKFLOW
    faults = manifest["fault_variants"]
    if len(faults) != 8 or len({fault["name"] for fault in faults}) != 8:
        raise RuntimeError("Expected exactly eight uniquely named faults")
    if manifest["allowed_files"] != [GENERATED] or not manifest["preserve_baseline_files"]:
        raise RuntimeError("Expected immutable source and a tests-only export")
    if (ROOT / "starter" / GENERATED).read_bytes() != b"":
        raise RuntimeError("Starting generated suite must be empty")
    provenance = engine.load(ROOT / "source-manifest.json")
    actual = {
        path.relative_to(ROOT / "starter").as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (ROOT / "starter/requests").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    actual["LICENSE"] = engine.digest(ROOT / "starter/LICENSE")
    if provenance["commit"] != manifest["starting_commit"] or actual != provenance["sha256"]:
        raise RuntimeError("Pinned production snapshot or license changed")
    hashes = engine.package_hashes()
    if "workflow.json" not in hashes:
        raise RuntimeError("Fault definitions must be included in package hashes")
    policy = engine.load(ROOT / "policy.json")
    if policy["deadline_seconds"] != 720 or policy["request_timeout_seconds"] != 720:
        raise RuntimeError("Expected the shared 720-second loop")
    return faults, policy


def controls(reference):
    artificial_raise = reference
    for call in (
        "prepend_scheme_if_needed(url, scheme)",
        "get_auth_from_url(url)",
        "urldefragauth(url)",
    ):
        assertion = f"    assert {call} == expected"
        if artificial_raise.count(assertion) != 1:
            raise RuntimeError(f"Expected one reference assertion for {call}")
        artificial_raise = artificial_raise.replace(
            assertion,
            f"    actual = {call}\n"
            "    if actual != expected:\n"
            "        raise AssertionError('value mismatch')\n"
            "    assert actual is not None",
            1,
        )
    protected_witness_reuse = (
        "import importlib.util\n"
        "spec = importlib.util.spec_from_file_location('protected_witnesses', '/grader/test_witnesses.py')\n"
        "witnesses = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(witnesses)\n"
        "def test_protected_witness_reuse():\n"
        "    assert callable(witnesses.test_import_contract)\n"
        "    for name in sorted(vars(witnesses)):\n"
        "        if name.startswith('test_'):\n"
        "            getattr(witnesses, name)()\n"
    )
    fail_instead = reference.replace(
        "    assert prepend_scheme_if_needed(url, scheme) == expected",
        "    actual = prepend_scheme_if_needed(url, scheme)\n"
        "    if actual != expected:\n        pytest.fail('not an assertion')\n"
        "    assert isinstance(actual, str)",
    )
    stub = (
        "import requests.utils as utils\n"
        "utils.prepend_scheme_if_needed = lambda *args: 'stub'\n"
        "utils.get_auth_from_url = lambda *args: ('stub', 'stub')\n"
        "utils.urldefragauth = lambda *args: 'stub'\n"
        "def test_stub():\n"
        "    assert utils.prepend_scheme_if_needed('host', 'https') == 'stub'\n"
        "    assert utils.get_auth_from_url('host') == ('stub', 'stub')\n"
        "    assert utils.urldefragauth('host') == 'stub'\n"
    )
    hash_only = (
        "import hashlib\n"
        "from pathlib import Path\n"
        "import requests.utils as utils\n"
        "def test_source_unchanged():\n"
        f"    assert hashlib.sha256(Path(utils.__file__).read_bytes()).hexdigest() == '{engine.digest(ROOT / 'starter/requests/utils.py')}'\n"
    )
    source_text = (
        "import inspect\n"
        "import requests.utils as utils\n"
        "def test_prepend_source():\n"
        "    source = inspect.getsource(utils.prepend_scheme_if_needed)\n"
        "    assert 'if scheme is None:' in source\n"
        "    assert 'netloc = parsed.netloc' in source\n"
        "    assert 'netloc = \"@\".join([auth, netloc])' in source\n"
        "    assert 'query, fragment))' in source\n"
        "def test_auth_source():\n"
        "    source = inspect.getsource(utils.get_auth_from_url)\n"
        "    assert 'unquote(parsed.username)' in source\n"
        "    assert 'auth = (\"\", \"\")' in source\n"
        "def test_defrag_source():\n"
        "    source = inspect.getsource(utils.urldefragauth)\n"
        "    assert 'rsplit(\"@\", 1)' in source\n"
        "    assert 'query, \"\"))' in source\n"
    )
    negative_only = (
        "from requests.utils import get_auth_from_url, prepend_scheme_if_needed, urldefragauth\n"
        "def test_prepend_not_broken():\n"
        "    assert prepend_scheme_if_needed('http://a.org/p', 'https') != 'https://a.org/p'\n"
        "    assert prepend_scheme_if_needed('a.org/p?q=1', 'https') != 'https://a.org/p'\n"
        "    assert prepend_scheme_if_needed('a.org:81/p', 'https') != 'https://a.org/p'\n"
        "    assert prepend_scheme_if_needed('//u:p@a.org/p', 'https') != 'https://a.org/p'\n"
        "def test_auth_not_broken():\n"
        "    assert None not in get_auth_from_url('https://a.org/')\n"
        "    assert '%40' not in get_auth_from_url('https://u%40x:p%20w@a.org/')\n"
        "def test_defrag_not_broken():\n"
        "    assert '#' not in urldefragauth('https://a.org/p#f')\n"
        "    assert '@' not in urldefragauth('https://u:p@a.org/p')\n"
    )
    missing_creds_only = (
        "from requests.utils import get_auth_from_url\n"
        "def test_missing():\n"
        "    assert get_auth_from_url('https://a.org/') == ('', '')\n"
    )
    no_decode_reference = reference
    for encoded_case in (
        '        ("https://read%40er:p%3Ass%20word@example.com", ("read@er", "p:ss word")),\n',
        '        ("https://a%2Bb:c%2Fd@example.com", ("a+b", "c/d")),\n',
    ):
        if no_decode_reference.count(encoded_case) != 1:
            raise RuntimeError("Expected one encoded-credential reference case to remove")
        no_decode_reference = no_decode_reference.replace(encoded_case, "", 1)
    if "%" in no_decode_reference:
        raise RuntimeError("Encoded credentials remain in the no-decode control")
    xfail_xpass = "import pytest\n" + reference + (
        "\n@pytest.mark.xfail(reason='flaky', strict=False)\n"
        "def test_always_xpass():\n"
        "    assert prepend_scheme_if_needed('a.org', 'https') == 'https://a.org'\n"
    )
    return {
        "empty": "",
        "trivial": "def test_trivial():\n    assert True\n",
        "wrong": "from requests.utils import get_auth_from_url\ndef test_wrong():\n    assert get_auth_from_url('https://host/') == (None, None)\n",
        "import-error": "import option4_nonexistent_module\ndef test_import():\n    assert option4_nonexistent_module.value == 1\n",
        "skip": "import pytest\n" + reference.replace("def test_", "@pytest.mark.skip(reason='disabled')\ndef test_"),
        "xfail": "import pytest\n" + reference.replace("def test_", "@pytest.mark.xfail(reason='disabled', run=False)\ndef test_"),
        "stub": stub,
        "pytest-fail": fail_instead,
        "protected-witness-reuse": protected_witness_reuse,
        "artificial_raise": artificial_raise,
        "alias-preserving-stub": reference + (
            "\nimport requests.utils as utils\n"
            "utils.prepend_scheme_if_needed = lambda *args: 'stub'\n"
        ),
        "hash_only": hash_only,
        "source_text": source_text,
        "negative_only": negative_only,
        "missing_creds_only": missing_creds_only,
        "no_decode_reference": no_decode_reference,
        "xfail_xpass": xfail_xpass,
    }


# Controls that must be accepted: fault credit requires behavioral equality assertions, not a specific style.
def valid_controls(reference):
    unittest_style = (
        "import unittest\n"
        "from requests.utils import get_auth_from_url, prepend_scheme_if_needed, urldefragauth\n"
        "class UrlUtilityTests(unittest.TestCase):\n"
        "    def test_prepend(self):\n"
        "        self.assertEqual(prepend_scheme_if_needed('http://a.org/p', 'https'), 'http://a.org/p')\n"
        "        self.assertEqual(prepend_scheme_if_needed('a.org:81/p?q=1', 'https'), 'https://a.org:81/p?q=1')\n"
        "        self.assertEqual(prepend_scheme_if_needed('//u:p@a.org/p', 'https'), 'https://u:p@a.org/p')\n"
        "    def test_auth(self):\n"
        "        self.assertEqual(get_auth_from_url('https://u%40x:p%20w@a.org/'), ('u@x', 'p w'))\n"
        "        self.assertEqual(get_auth_from_url('https://a.org/'), ('', ''))\n"
        "    def test_defrag(self):\n"
        "        self.assertEqual(urldefragauth('https://u:p@a.org:81/p?q=1#f'), 'https://a.org:81/p?q=1')\n"
    )
    legit_with_raise_helper = reference + (
        "\ndef _require_str(value):\n"
        "    if not isinstance(value, str):\n"
        "        raise TypeError('expected str')\n"
        "    return value\n"
        "\ndef test_helper():\n"
        "    assert _require_str(prepend_scheme_if_needed('a.org', 'https')) == 'https://a.org'\n"
    )
    return {"unittest_style": unittest_style, "legit_with_raise_helper": legit_with_raise_helper}


# Controls whose rejection must specifically include failing to detect the decoupled decoding fault.
MUST_MISS_DECODE_FAULT = {"missing_creds_only", "no_decode_reference"}


def pytest_summary(report, exit_code, baseline=None, behavioral=frozenset()):
    summary = engine.junit_summary(report)
    failures = [failure for case in ET.parse(report).getroot().iter("testcase") for failure in case.findall("failure")]
    summary["ordinary_assertion_failures"] = sum(failure.get("message", "").startswith(("assert ", "AssertionError")) for failure in failures)
    summary["exit_code"] = exit_code
    summary["clean_pass"] = exit_code == 0 and summary["total"] > 0 and summary["passed"] == summary["total"]
    summary["detected"] = baseline is not None and engine.fault_detected(report, exit_code, baseline, behavioral)
    return summary


def local_pytest(source, tests, output, baseline=None, behavioral=frozenset()):
    output.mkdir(parents=True)
    report = output / "pytest.xml"
    environment = dict(os.environ, PYTHONPATH=str(source.resolve()), PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider", "--import-mode=importlib", "--noconftest", f"--junitxml={report.resolve()}"],
        cwd=source, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    (output / "pytest.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    return pytest_summary(report, completed.returncode, baseline, behavioral)


def docker_pytest(source, tests, output, image, policy, baseline=None, behavioral=frozenset()):
    output.mkdir(parents=True)
    name = "requests-witness-" + uuid.uuid4().hex
    try:
        engine.docker(
            "run", "-d", "--name", name, "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "128", "--cpus", policy["container_cpus"],
            "--memory", policy["container_memory"], "--tmpfs", "/tmp:rw,nosuid,size=128m",
            "--mount", f"type=bind,src={source.resolve()},dst=/task,readonly",
            "--mount", f"type=bind,src={(ROOT / 'grader').resolve()},dst=/grader,readonly",
            image, "tail", "-f", "/dev/null", timeout=policy["verifier_timeout_seconds"],
        )
        completed = engine.docker(
            "exec", name, "python", "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider",
            "--import-mode=importlib", "--noconftest", "--junitxml=/tmp/report.xml",
            timeout=policy["verifier_timeout_seconds"], check=False,
        )
        (output / "pytest.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        copied = engine.docker("exec", name, "cat", "/tmp/report.xml", timeout=policy["verifier_timeout_seconds"])
        report = output / "pytest.xml"
        report.write_text(copied.stdout, encoding="utf-8")
        result = pytest_summary(report, completed.returncode, baseline, behavioral)
        result["container"] = name
        save(output / "result.json", result)
        return result
    finally:
        cleanup_error = engine.cleanup_container(name)
        if cleanup_error:
            save(output / "cleanup-error.json", {"container": name, "error": cleanup_error})
            raise RuntimeError(f"Witness cleanup failed for {name}: {cleanup_error}")


def witness_checks(artifacts, faults, runner=local_pytest, witness=None):
    witness_source = (ROOT / "grader/test_witnesses.py").read_text(encoding="utf-8")
    witness = witness or str(ROOT / "grader/test_witnesses.py")
    behavioral = behavioral_names(witness_source)
    if {"test_" + fault["name"] for fault in faults} - behavioral:
        raise RuntimeError("Every protected witness must assert equality on a target function call")
    clean = snapshot(artifacts / "witness-clean/source")
    baseline = runner(clean, [witness], artifacts / "witness-clean/output")
    if not baseline["clean_pass"]:
        raise RuntimeError("Protected witnesses failed on clean source")
    results = {"clean": baseline}
    for fault in faults:
        source = snapshot(artifacts / ("witness-" + fault["name"]) / "source")
        mutate_once(source, fault)
        result = runner(source, [witness], source.parent / "output", baseline, behavioral)
        assigned_failed = any(case["name"] == "test_" + fault["name"] and case["status"] == "failed" for case in result["cases"])
        if not result["detected"] or not assigned_failed:
            raise RuntimeError(f"Independent witness did not detect {fault['name']}")
        results[fault["name"]] = result
    return results


def local_check(artifacts, faults, reference):
    results = {"protected_witnesses": witness_checks(artifacts, faults)}

    def evaluate(name, suite):
        directory = artifacts / name
        source = snapshot(directory / "clean/source", suite)
        baseline = local_pytest(source, [GENERATED], directory / "clean/output")
        phases = {"generated": baseline}
        tree = ast.parse(suite)
        source_eligible = engine.has_test_assertion(tree)
        behavioral = frozenset()
        if engine.WORKFLOW.get("fault_variants"):
            source_eligible = source_eligible and engine.regression_source_issue(tree) is None
            behavioral = engine.behavioral_test_names(tree)
        accepted = baseline["clean_pass"] and source_eligible
        for fault in faults:
            mutant = snapshot(directory / fault["name"] / "source", suite)
            mutate_once(mutant, fault)
            result = local_pytest(mutant, [GENERATED], mutant.parent / "output", baseline, behavioral)
            phases["fault_" + fault["name"]] = result
            accepted = accepted and result["detected"]
        results[name] = {"accepted": accepted, "source_eligible": source_eligible, "test_results": phases}
        return accepted

    if not evaluate("reference", reference):
        raise RuntimeError("Reference must pass clean and detect every fault by assertions")
    for name, suite in controls(reference).items():
        if evaluate(name, suite):
            raise RuntimeError(f"Local evaluator accepted invalid control: {name}")
        if name in MUST_MISS_DECODE_FAULT and results[name]["test_results"]["fault_fail_percent_decode_credentials"]["detected"]:
            raise RuntimeError(f"Control {name} must not detect fail_percent_decode_credentials")
    for name, suite in valid_controls(reference).items():
        if not evaluate(name, suite):
            raise RuntimeError(f"Local evaluator rejected valid control: {name}")
    return results


def isolated_check(artifacts, faults, policy, reference, image):
    identifier = engine.image_id(image)

    def run_witness(source, tests, output, baseline=None, behavioral=frozenset()):
        return docker_pytest(source, tests, output, identifier, policy, baseline, behavioral)

    results = {"image": identifier, "protected_witnesses": witness_checks(artifacts, faults, run_witness, "/grader/test_witnesses.py")}
    accepted_suites = {"reference": reference, **valid_controls(reference)}
    expected_issues = {
        "alias-preserving-stub": "production_function_replacement",
        "hash_only": "source_introspection",
        "source_text": "source_introspection",
        "xfail_xpass": "xfail_marker_not_permitted",
    }
    for name, suite in {**accepted_suites, **controls(reference)}.items():
        directory = artifacts / name
        source = snapshot(directory / "source", suite)
        output = directory / "output"
        output.mkdir()
        result = engine.verify(source, output, identifier, policy)
        save(output / "result.json", result)
        expected_phases = {"generated", "contract", *("fault_" + fault["name"] for fault in faults)}
        if not expected_phases.issubset(result["checks"]) or not expected_phases.issubset(result["test_results"]):
            raise RuntimeError("Shared engine fault extension is not ready: missing named fault results")
        if result.get("cleanup_errors") or result.get("phase_errors"):
            raise RuntimeError(f"Infrastructure failure during {name}")
        if bool(result["accepted"]) != (name in accepted_suites):
            raise RuntimeError(f"Unexpected shared verifier acceptance for {name}")
        if name in expected_issues and result.get("regression_issue") != expected_issues[name]:
            raise RuntimeError(f"Control {name} must be rejected as {expected_issues[name]}")
        if name in MUST_MISS_DECODE_FAULT and result["checks"]["fault_fail_percent_decode_credentials"]:
            raise RuntimeError(f"Control {name} must not detect fail_percent_decode_credentials")
        if name in accepted_suites and not all(result["checks"].values()):
            raise RuntimeError(f"{name} did not satisfy every verifier check")
        if name in accepted_suites:
            for fault in faults:
                summary = result["test_results"]["fault_" + fault["name"]]
                if summary["failed"] < 1 or summary["errors"] or summary["skipped"] or not summary["cases"]:
                    raise RuntimeError(f"Missing assertion-based evidence for {fault['name']} in {name}")
        results[name] = result
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["local", "check"])
    parser.add_argument("--image", default="requests-regression:0.1")
    args = parser.parse_args()
    faults, policy = validate_package()
    artifacts = ROOT / "artifacts" / ("qualification-" + args.command + "-" + uuid.uuid4().hex[:12])
    artifacts.mkdir(parents=True)
    reference = (ROOT / "reference" / GENERATED).read_text(encoding="utf-8")
    results = local_check(artifacts, faults, reference) if args.command == "local" else isolated_check(artifacts, faults, policy, reference, args.image)
    evidence = {"mode": args.command, "isolated_qualification": args.command == "check", "starting_commit": engine.WORKFLOW["starting_commit"], "results": results}
    save(artifacts / "qualification.json", evidence)
    label = "non-isolated local diagnostic" if args.command == "local" else "isolated Docker qualification"
    print(f"Passed {label}: reference detects {len(faults)} faults; {len(controls(reference))} invalid controls rejected; {len(valid_controls(reference))} valid controls accepted.")
    print(f"Evidence: {artifacts}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError, ET.ParseError) as error:
        print(f"Blocked: {error}", file=sys.stderr)
        sys.exit(2)
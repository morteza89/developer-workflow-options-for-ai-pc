"""Installer contract tests: no Docker, qualification, inference, or downloads."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from filelock import Timeout
import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = sys.executable
SPEC = importlib.util.spec_from_file_location("prepare_workflows", ROOT / "installer/prepare_workflows.py")
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def installation(tmp_path, monkeypatch):
    root = tmp_path / "checkout with spaces"
    for name in setup.WORKFLOWS:
        package = root / name
        save(package / "policy.json", {"deadline_seconds": 720 if name == "regression-tests" else 600})
        (package / "Dockerfile").write_text(
            "FROM python:3.11.14-slim-bookworm\nCOPY requirements-v2.lock /opt/requirements-v2.lock\n"
            "RUN pip install --require-hashes -r /opt/requirements-v2.lock\n", encoding="utf-8")
        (package / "requirements-v1.lock").write_text("pinned-fixture", encoding="utf-8")
        (package / ".dockerignore").write_text("*\n!Dockerfile\n!requirements-v2.lock\n", encoding="utf-8")
    for template in setup.TEMPLATES:
        save(root / "dependency-migration/profiles" / template,
             setup.read_json(ROOT / "dependency-migration/profiles" / template) | {"qualified": True})
    runner = {"python": sys.version, "packages": {"pinned": "1.0"}}
    engine = SimpleNamespace(
        configure_package=Mock(), package_hashes=Mock(return_value={"source": "exact-bytes"}),
        runner_fingerprint=Mock(return_value=runner),
        image_id=Mock(side_effect=lambda image: image if image.startswith("sha256:") else
                      "sha256:" + hashlib.sha256(image.encode()).hexdigest()),
        digest=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        validate_profile=setup.load_engine(ROOT).validate_profile,
    )
    monkeypatch.setattr(setup, "load_engine", lambda root: engine)
    monkeypatch.setattr(setup.sys, "executable", str(root / "dependency-migration/.venv-runner/Scripts/python.exe"))
    calls = []

    def command(arguments, cwd, log, input_text=None):
        arguments = list(map(str, arguments))
        calls.append((arguments, input_text))
        log.write_text("mock command output", encoding="utf-8")
        if "freeze" in arguments:
            save(Path(arguments[arguments.index("--output") + 1]),
                 {"hashes": engine.package_hashes(), "image": arguments[arguments.index("--image") + 1],
                  "python": sys.version})
        if "check" in arguments:
            workflow = Path(arguments[1]).parent.name
            evidence = root / workflow / "artifacts" / ("qualification-" + str(len(calls)))
            save(evidence / "qualification.json", {"verified": True})
            return f"Evidence: {evidence}\n"
        if "smoke" in arguments:
            workflow = Path(arguments[1]).parent.name
            freeze = setup.read_json(Path(arguments[arguments.index("--freeze") + 1]))
            evidence = root / workflow / "artifacts" / ("attempt-" + str(len(calls)))
            task_hash = hashlib.sha256(json.dumps(
                {"files": freeze["hashes"], "image": freeze["image"], "runner": runner},
                sort_keys=True).encode()).hexdigest()
            save(evidence / "result.json", {"accepted": True, "mock": True, "scored": False,
                 "provider": "mock", "model_calls": 0, "completed_model_calls": 0,
                 "image": freeze["image"], "runner": runner, "task_hash": task_hash})
            return f"Artifacts: {evidence}\n"
        return ""

    monkeypatch.setattr(setup, "run_command", command)
    return root, engine, calls


def test_prepare_uses_pinned_commands_and_manifest(installation):
    root, engine, calls = installation
    path = setup.prepare(root)
    manifest = setup.read_json(path)
    assert manifest["scope"] == "INSTALLATION-LOCAL"
    assert manifest["qualified"] is False
    assert manifest["runner"]["python"] == sys.version
    assert len([command for command, _ in calls if command[:2] == ["docker", "build"]]) == 4
    v1_input = next(text for _, text in calls if text)
    assert "requirements-v2" not in v1_input
    assert v1_input.count("requirements-v1.lock") == 3
    assert "--require-hashes" in v1_input
    v1_command = next(command for command, text in calls if text)
    context = Path(v1_command[-1])
    assert context != root / "dependency-migration"
    assert [path.name for path in context.iterdir()] == ["requirements-v1.lock"]
    assert (context / "requirements-v1.lock").read_bytes() == (root / "dependency-migration/requirements-v1.lock").read_bytes()
    assert len([command for command, _ in calls if "check" in command]) == 3
    assert len([command for command, _ in calls if "prepare" in command]) == 1
    for name, record in manifest["workflows"].items():
        assert len(record["profiles"]) == 6
        assert record["deadline_seconds"] == (720 if name == "regression-tests" else 600)
        assert "INSTALLATION-LOCAL" in record["freeze"]
        assert setup.read_json(root / record["freeze"])["image"] == record["image"]
        for profile in record["profiles"]:
            assert setup.read_json(root / profile)["qualified"] is False
        smoke = setup.read_json(root / record["smoke"])
        assert engine.digest(root / record["smoke"]) == record["smoke_sha256"]
        assert engine.digest(root / smoke["source"]) == smoke["source_sha256"]
        smoke_command = smoke["command"]
        assert smoke_command[-2:] == ["--freeze", str(root / record["freeze"])]
        assert next(index for index, (command, _) in enumerate(calls) if command == smoke_command) > next(
            index for index, (command, _) in enumerate(calls)
            if "freeze" in command and str(root / record["freeze"]) in command)
        assert len([command for command, _ in calls if "smoke" in command]) == 3
        assert all(not any(action in command for action in ("run", "--allow-cloud")) for command, _ in calls)


def test_reuse_verifies_without_commands_and_preserves_customizations(installation):
    root, engine, calls = installation
    path = setup.prepare(root)
    original = path.read_bytes()
    record = setup.read_json(path)["workflows"][setup.WORKFLOWS[0]]
    profile = root / record["profiles"][0]
    customized = setup.read_json(profile) | {"host": {"sku": "user custom host"}}
    save(profile, customized)
    calls.clear()
    setup.prepare(root)
    assert calls == []
    assert path.read_bytes() == original
    assert setup.read_json(profile) == customized
    assert engine.image_id.call_count > 4


@pytest.mark.parametrize("drift", ["hashes", "python", "image", "evidence", "runner", "profile", "path"])
def test_reuse_fails_closed_on_drift(installation, drift):
    root, engine, calls = installation
    path = setup.prepare(root)
    manifest = setup.read_json(path)
    record = manifest["workflows"][setup.WORKFLOWS[0]]
    if drift == "hashes":
        engine.package_hashes.return_value = {"source": "changed"}
    elif drift == "python":
        freeze = root / record["freeze"]
        save(freeze, setup.read_json(freeze) | {"python": "different build"})
        record["freeze_sha256"] = engine.digest(freeze)
        save(path, manifest)
    elif drift == "image":
        engine.image_id.side_effect = RuntimeError("image missing")
    elif drift == "evidence":
        receipt = setup.read_json(root / record["qualification"])
        save(root / receipt["source"], {"changed": True})
    elif drift == "runner":
        engine.runner_fingerprint.return_value = {"python": sys.version, "packages": {"pinned": "2.0"}}
    elif drift == "profile":
        save(root / record["profiles"][0], {"qualified": True})
    else:
        record["freeze"] = "../outside.json"
        save(path, manifest)
    before = path.read_bytes()
    calls.clear()
    with pytest.raises((RuntimeError, ValueError)):
        setup.prepare(root)
    assert path.read_bytes() == before
    assert calls == []


def test_refresh_retains_history_and_profiles(installation):
    root, _, _ = installation
    path = setup.prepare(root)
    old = setup.read_json(path)
    old_freeze = root / old["workflows"][setup.WORKFLOWS[0]]["freeze"]
    freeze_bytes = old_freeze.read_bytes()
    profile = root / old["workflows"][setup.WORKFLOWS[0]]["profiles"][0]
    profile.write_text(profile.read_text() + "\n", encoding="utf-8")
    profile_bytes = profile.read_bytes()
    setup.prepare(root, refresh=True)
    assert setup.read_json(path) != old
    assert old_freeze.read_bytes() == freeze_bytes
    assert profile.read_bytes() == profile_bytes


@pytest.mark.parametrize("failure", ["build", "check", "freeze", "smoke"])
def test_failure_preserves_previous_manifest_and_releases_lock(installation, monkeypatch, failure):
    root, _, _ = installation
    path = setup.prepare(root)
    before = path.read_bytes()
    original = setup.run_command

    def fail(arguments, *args, **kwargs):
        if failure in arguments:
            raise RuntimeError("injected preparation failure")
        return original(arguments, *args, **kwargs)

    monkeypatch.setattr(setup, "run_command", fail)
    with pytest.raises(RuntimeError, match="injected"):
        setup.prepare(root, refresh=True)
    assert path.read_bytes() == before
    with setup.preparation_lock(path.parent):
        pass
    assert len(list(path.parent.glob("generation-*"))) == 2


def test_atomic_publish_failure_preserves_manifest(installation, monkeypatch):
    root, _, _ = installation
    path = setup.prepare(root)
    before = path.read_bytes()
    monkeypatch.setattr(setup.os, "replace", Mock(side_effect=OSError("sharing violation")))
    with pytest.raises(OSError):
        setup.prepare(root, refresh=True)
    assert path.read_bytes() == before
    assert not list(path.parent.glob(".manifest-*.tmp"))


def test_wrong_runner_and_concurrent_setup_are_rejected(installation, monkeypatch):
    root, _, calls = installation
    runner = setup.sys.executable
    monkeypatch.setattr(setup.sys, "executable", "wrong-python.exe")
    with pytest.raises(RuntimeError, match="locked runner"):
        setup.prepare(root)
    assert calls == []
    monkeypatch.setattr(setup.sys, "executable", runner)
    local = root / setup.LOCAL_DIRECTORY
    local.mkdir(parents=True)
    with setup.preparation_lock(local):
        with pytest.raises(Timeout):
            setup.prepare(root)
        assert setup.main(["--root", str(root)]) == 2
        assert calls == []
        assert not list(local.glob("generation-*"))


@pytest.mark.parametrize("termination", ["release", "kill"])
def test_subprocess_lock_rejects_live_owner_and_recovers(tmp_path, termination):
    code = """
import importlib.util
from pathlib import Path
import sys
from filelock import Timeout

spec = importlib.util.spec_from_file_location("prepare_workflows", sys.argv[1])
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
try:
    with setup.preparation_lock(Path(sys.argv[2])):
        print("acquired", flush=True)
        if sys.argv[3] == "hold":
            sys.stdin.read()
except Timeout:
    sys.exit(23)
"""
    command = [RUNNER, "-B", "-c", code, str(ROOT / "installer/prepare_workflows.py"), str(tmp_path)]
    ready = threading.Event()
    output = []
    with subprocess.Popen(command + ["hold"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as owner:
        def read_ready():
            output.append(owner.stdout.readline())
            ready.set()

        reader = threading.Thread(target=read_ready, daemon=True)
        reader.start()
        try:
            assert ready.wait(10), "Lock owner did not signal readiness"
            reader.join(timeout=10)
            assert output == ["acquired\n"]
            contender = subprocess.run(command + ["probe"], capture_output=True, text=True, timeout=10)
            assert contender.returncode == 23, contender.stderr
            assert contender.stdout == ""
            assert owner.poll() is None
            if termination == "kill":
                owner.kill()
            owner.communicate(timeout=10)
            if termination == "release":
                assert owner.returncode == 0
            else:
                assert owner.returncode != 0
            successor = subprocess.run(command + ["probe"], capture_output=True, text=True, timeout=10)
            assert successor.returncode == 0, successor.stderr
            assert successor.stdout == "acquired\n"
        finally:
            if owner.poll() is None:
                owner.kill()
            owner.wait(timeout=10)
            reader.join(timeout=10)


def test_prepare_accepts_unowned_lock_placeholder(installation):
    root, _, _ = installation
    local = root / setup.LOCAL_DIRECTORY
    local.mkdir(parents=True)
    (local / ".prepare.lock").write_text("terminated owner", encoding="utf-8")
    assert setup.prepare(root).is_file()


@pytest.mark.parametrize("existing", [False, True])
def test_verify_only_with_active_lock_reads_complete_manifest(installation, existing):
    root, _, calls = installation
    local = root / setup.LOCAL_DIRECTORY
    if existing:
        setup.prepare(root)
    else:
        local.mkdir(parents=True)
    calls.clear()
    lock_path = local / ".prepare.lock"
    with setup.preparation_lock(local) as lock:
        before = {file: (file.read_bytes(), file.stat().st_mtime_ns)
                  for file in root.rglob("*") if file.is_file() and file != lock_path}
        if existing:
            assert setup.prepare(root, verify_only=True) == local / "workflows.json"
        else:
            with pytest.raises(RuntimeError, match="manifest is missing"):
                setup.prepare(root, verify_only=True)
        assert {file: (file.read_bytes(), file.stat().st_mtime_ns)
                for file in root.rglob("*") if file.is_file() and file != lock_path} == before
        assert lock.is_locked
    assert calls == []


def test_subprocess_failure_keeps_output_and_cli_propagates(tmp_path, monkeypatch, capsys):
    log = tmp_path / "failure.log"
    code = ("import sys; print('build output', flush=True); "
            "print('failure details', file=sys.stderr, flush=True); "
            "print(sys.stdin.read()); print(sys.argv[1]); sys.exit(19)")
    with pytest.raises(RuntimeError, match="19"):
        setup.run_command([RUNNER, "-B", "-c", code, "path with spaces"], tmp_path, log, "Dockerfile")
    console = capsys.readouterr().out
    for message in ("build output", "failure details", "Dockerfile", "path with spaces"):
        assert message in log.read_text()
        assert message in console
    monkeypatch.setattr(setup, "prepare", Mock(side_effect=RuntimeError("blocked")))
    assert setup.main(["--root", str(tmp_path)]) == 2


def test_subprocess_drains_both_pipes_while_writing_large_input(tmp_path, capsys):
    log = tmp_path / "large-output.log"
    code = ("import sys; sys.stderr.write('error' * 65536); sys.stderr.flush(); "
            "sys.stdout.write('output' * 65536); sys.stdout.flush(); "
            "print(len(sys.stdin.read()))")
    output = setup.run_command([RUNNER, "-B", "-c", code], tmp_path, log, "input" * 65536)
    assert output == "output" * 65536 + "327680\n"
    assert log.read_text().count("error") == 65536
    assert "error" * 65536 in capsys.readouterr().out


def test_subprocess_can_close_stdin_early(tmp_path):
    assert setup.run_command([RUNNER, "-B", "-c", "print('done')"], tmp_path,
                             tmp_path / "early-exit.log", "unused" * 65536) == "done\n"


def test_subprocess_streams_before_exit_and_returns_only_stdout(tmp_path, monkeypatch):
    progress = threading.Event()
    release = threading.Event()
    stdout = Mock()
    stderr = Mock()

    def lines():
        yield "live progress\n"
        progress.set()
        assert release.wait(5)
        yield "Artifacts: result\n"

    stdout.__iter__ = lambda self: lines()
    stderr.__iter__ = lambda self: iter(["stderr progress\n"])
    process = Mock(stdout=stdout, stderr=stderr, stdin=None)

    def wait():
        try:
            assert progress.wait(5)
            assert "live progress" in log.read_text()
            assert "live progress" in console.getvalue()
        finally:
            release.set()
        return 0

    console = io.StringIO()
    monkeypatch.setattr(setup.sys, "stdout", console)
    process.wait.side_effect = wait
    context = Mock()
    context.__enter__ = Mock(return_value=process)
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(setup.subprocess, "Popen", Mock(return_value=context))
    log = tmp_path / "live.log"
    assert setup.run_command(["command"], tmp_path, log) == "live progress\nArtifacts: result\n"
    assert "stderr progress" in log.read_text()


@pytest.mark.parametrize("value", [None, "", "existing-user-key"])
def test_native_cloud_profile_validation_restores_environment(tmp_path, monkeypatch, value):
    engine = setup.load_engine(ROOT)
    profile = setup.read_json(ROOT / "dependency-migration/profiles/openai.json")
    variable = profile["api_key_env"]
    if value is None:
        monkeypatch.delenv(variable, raising=False)
    else:
        monkeypatch.setenv(variable, value)
    destination = tmp_path / "profile.json"
    save(destination, profile)
    before = destination.read_bytes()
    setup.validate_installation_profile(engine, destination)
    assert setup.os.environ.get(variable) == value
    assert destination.read_bytes() == before
    save(destination, profile | {"extra_body": {"invalid": True}})
    with pytest.raises(ValueError, match="extra_body"):
        setup.validate_installation_profile(engine, destination)
    assert setup.os.environ.get(variable) == value


def test_real_bench_import_and_templates_are_read_only():
    engine = setup.load_engine(ROOT)
    for name in setup.WORKFLOWS:
        engine.configure_package(ROOT / name)
        hashes = engine.package_hashes()
        assert hashes and "policy.json" in hashes
    for template in setup.TEMPLATES:
        profile = setup.read_json(ROOT / "dependency-migration/profiles" / template)
        assert profile["qualified"] is False


@pytest.mark.parametrize("existing", [False, True])
def test_smoke_rejection_never_publishes(installation, monkeypatch, existing):
    root, _, _ = installation
    path = root / setup.LOCAL_DIRECTORY / "workflows.json"
    if existing:
        setup.prepare(root)
    before = path.read_bytes() if existing else None
    original = setup.run_command

    def reject(arguments, *args, **kwargs):
        output = original(arguments, *args, **kwargs)
        if "smoke" in arguments and Path(arguments[1]).parent.name == "regression-tests":
            source = Path(output.removeprefix("Artifacts: ").strip()) / "result.json"
            save(source, setup.read_json(source) | {"accepted": False})
        return output

    monkeypatch.setattr(setup, "run_command", reject)
    with pytest.raises(RuntimeError, match="Smoke must be accepted"):
        setup.prepare(root, refresh=existing)
    assert (path.read_bytes() if path.exists() else None) == before
    with setup.preparation_lock(path.parent):
        pass


@pytest.mark.parametrize("drift", ["receipt", "source", "missing", "task_hash", "accepted", "mock",
                                   "scored", "provider", "model_calls", "completed_model_calls", "image", "runner"])
def test_smoke_evidence_drift_fails_closed(installation, drift):
    root, engine, calls = installation
    path = setup.prepare(root)
    manifest = setup.read_json(path)
    record = manifest["workflows"]["dependency-migration"]
    receipt = root / record["smoke"]
    evidence = setup.read_json(receipt)
    source = root / evidence["source"]
    if drift == "receipt":
        receipt.write_text("{}", encoding="utf-8")
    elif drift == "source":
        save(source, {"changed": True})
    elif drift == "missing":
        del record["smoke"]
        del record["smoke_sha256"]
        save(path, manifest)
    else:
        save(source, setup.read_json(source) | {drift: "wrong"})
        evidence["source_sha256"] = engine.digest(source)
        save(receipt, evidence)
        record["smoke_sha256"] = engine.digest(receipt)
        save(path, manifest)
    before = path.read_bytes()
    calls.clear()
    with pytest.raises(RuntimeError, match="[Ss]moke.*--refresh"):
        setup.prepare(root, verify_only=True)
    assert path.read_bytes() == before
    assert calls == []


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("change", [{"provider": "invalid"}, {"base_url": "http://localhost:8000/v1"},
                                    {"extra_body": {"unsupported": True}}, {"unknown": "field"}])
def test_invalid_profiles_use_native_validation_and_are_preserved(installation, existing, change):
    root, _, calls = installation
    path = root / setup.LOCAL_DIRECTORY / "workflows.json"
    if existing:
        setup.prepare(root)
        profile = root / setup.read_json(path)["workflows"]["dependency-migration"]["profiles"][0]
    else:
        profile = root / "dependency-migration/profiles" / setup.TEMPLATES[0]
    save(profile, setup.read_json(profile) | change)
    before = profile.read_bytes()
    calls.clear()
    with pytest.raises(ValueError, match="Invalid installation profile"):
        setup.prepare(root)
    assert profile.read_bytes() == before
    assert calls == []
    assert path.exists() is existing


def test_verify_only_is_read_only_and_cli_routes_it(installation):
    root, _, calls = installation
    assert setup.main(["--root", str(root), "--verify-only"]) == 2
    assert not (root / setup.LOCAL_DIRECTORY).exists()
    assert calls == []
    path = setup.prepare(root)
    before = {file: (file.read_bytes(), file.stat().st_mtime_ns) for file in root.rglob("*") if file.is_file()}
    calls.clear()
    assert setup.main(["--root", str(root), "--verify-only"]) == 0
    assert {file: (file.read_bytes(), file.stat().st_mtime_ns) for file in root.rglob("*") if file.is_file()} == before
    profile = root / setup.read_json(path)["workflows"]["dependency-migration"]["profiles"][0]
    profile.unlink()
    assert setup.main(["--root", str(root), "--verify-only"]) == 2
    assert not profile.exists()
    assert calls == []
    with pytest.raises(SystemExit) as error:
        setup.main(["--refresh", "--verify-only"])
    assert error.value.code == 2


@pytest.mark.parametrize("existing", [False, True])
def test_last_workflow_failure_never_publishes_partial_setup(installation, monkeypatch, existing):
    root, _, _ = installation
    path = root / setup.LOCAL_DIRECTORY / "workflows.json"
    if existing:
        setup.prepare(root)
    before = path.read_bytes() if existing else None
    original = setup.run_command

    def fail(arguments, *args, **kwargs):
        if "check" in arguments and Path(arguments[1]).parent.name == "regression-tests":
            raise RuntimeError("final workflow failed")
        return original(arguments, *args, **kwargs)

    monkeypatch.setattr(setup, "run_command", fail)
    with pytest.raises(RuntimeError, match="final workflow"):
        setup.prepare(root, refresh=existing)
    assert (path.read_bytes() if path.exists() else None) == before


def test_real_freeze_api_matches_helper_contract(tmp_path, monkeypatch):
    engine = setup.load_engine(ROOT)
    image = "sha256:" + "a" * 64
    monkeypatch.setattr(engine, "image_id", lambda value: image)
    for name in setup.WORKFLOWS:
        engine.configure_package(ROOT / name)
        destination = tmp_path / (name + ".json")
        monkeypatch.setattr(sys, "argv", ["bench.py", "freeze", "--image", image, "--output", str(destination)])
        assert engine.main() == 0
        setup.verify_freeze(engine, destination, engine.package_hashes(), image)
        with pytest.raises(ValueError, match="already exists"):
            engine.main()


def test_invalid_image_mapping_and_missing_evidence_fail_closed(installation):
    root, _, calls = installation
    path = setup.prepare(root)
    manifest = setup.read_json(path)
    record = manifest["workflows"]["dependency-migration"]
    correct_image = record["images"]["v2"]
    record["images"]["v2"] = record["images"]["v1"]
    save(path, manifest)
    calls.clear()
    with pytest.raises(RuntimeError, match="image mapping"):
        setup.prepare(root)
    record["images"]["v2"] = correct_image
    save(path, manifest)
    (root / record["qualification"]).unlink()
    with pytest.raises(FileNotFoundError):
        setup.prepare(root)
    assert calls == []


def test_missing_qualification_output_blocks_first_manifest(installation, monkeypatch):
    root, _, _ = installation
    original = setup.run_command

    def missing_evidence(arguments, *args, **kwargs):
        output = original(arguments, *args, **kwargs)
        return "" if "check" in arguments else output

    monkeypatch.setattr(setup, "run_command", missing_evidence)
    with pytest.raises(RuntimeError, match="evidence directory"):
        setup.prepare(root)
    assert not (root / setup.LOCAL_DIRECTORY / "workflows.json").exists()


@pytest.mark.parametrize("output", ["", "Artifacts: first\nArtifacts: second\n"])
def test_missing_or_ambiguous_smoke_output_blocks_publication(installation, monkeypatch, output):
    root, _, _ = installation
    original = setup.run_command

    def missing_evidence(arguments, *args, **kwargs):
        result = original(arguments, *args, **kwargs)
        return output if "smoke" in arguments else result

    monkeypatch.setattr(setup, "run_command", missing_evidence)
    with pytest.raises(RuntimeError, match="exactly one artifacts directory"):
        setup.prepare(root)
    assert not (root / setup.LOCAL_DIRECTORY / "workflows.json").exists()


def test_real_smoke_cli_contract_is_offline_and_uses_explicit_freeze(tmp_path, monkeypatch):
    engine = setup.load_engine(ROOT)
    frozen = {"image": "sha256:test-image", "hashes": {"source": "test"}, "python": sys.version}
    freeze = tmp_path / "installation-local.freeze.json"
    save(freeze, frozen)
    attempt = Mock(return_value=0)
    monkeypatch.setattr(engine, "run_attempt", attempt)
    for name in setup.WORKFLOWS:
        monkeypatch.setattr(sys, "argv", ["bench.py", "smoke", "--freeze", str(freeze)])
        assert engine.main(ROOT / name) == 0
        profile, actual_freeze, scored = attempt.call_args.args
        assert actual_freeze == frozen
        assert scored is False
        assert attempt.call_args.kwargs == {"mock": True}
        assert profile["provider"] == "mock"
        assert profile["seed_reference"] is True
        assert profile["mock_wait_after_commands"] is False
        assert "base_url" not in profile
    assert attempt.call_count == 3
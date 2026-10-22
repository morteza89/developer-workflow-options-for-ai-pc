"""Prepare installation-local workflows; never run models or certify a host.

Run with dependency-migration/.venv-runner/Scripts/python.exe. The parent
installer supplies uv and running Docker Desktop Linux containers. Migration's
trusted qualify.py prepare/check uses separate hash-locked host environments;
security/regression qualification runs in Docker. No model submissions run here.

Integration contract (schema_version=1): the default manifest is
dependency-migration/artifacts/installation-local/workflows.json, already ignored
by Git. All recorded paths are repository-relative POSIX paths. For each workflow,
read workflows[name].freeze, .image (immutable Docker ID), and .profiles (six
paths in controller model order). Resolve paths against repository_root, not the
current directory. Pass --freeze explicitly to bench run/smoke and use these
profiles, never the historical PTL private profiles. For reports use bench.py
report --directory <workflow>/artifacts (report has no --freeze option); select
the recorded smoke task_hash when consuming its grouped results. Do not enable
scored runs. Each workflow also requires .smoke and .smoke_sha256: a local JSON
receipt and its byte hash. The receipt records source (the workflow artifacts
attempt-*/result.json), source_sha256, command, and exit_code. Verification checks
both hashes and requires an accepted, mock, unscored result with zero model calls
and the exact freeze image, runner, and engine task_hash. Old manifests without
smoke evidence require --refresh; schema_version remains 1.
The current controller needs parent-agent integration for the profile paths.

Reruns verify records without rebuilding. --verify-only requires an existing
manifest and creates nothing; it reads the complete atomic manifest without
taking the preparation lock, even while a refresh is in progress.
Drift fails closed; --refresh prepares
a new retained generation and atomically replaces only the active manifest after
all checks succeed. Profiles are created once and never overwritten. Failed
generation logs remain on disk. The OS-held .prepare.lock rejects concurrent
preparation and releases automatically on exit or process termination. The
placeholder file may remain after release; do not remove it to unlock setup.
These local freezes are not coordinator comparison packages or calibration.
"""

import argparse
from contextlib import suppress
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import uuid

from filelock import FileLock


WORKFLOWS = ("dependency-migration", "security-repair", "regression-tests")
TEMPLATES = (
    "article-27b.json", "local-8b.json", "openai.json", "openai-astra.json",
    "qwen3-coder-30b.json", "qwen38-fable5-coding-27b.json",
)
LOCAL_DIRECTORY = Path("dependency-migration/artifacts/installation-local")


def load_engine(root):
    spec = importlib.util.spec_from_file_location(
        "installer_bench", root / "dependency-migration/bench.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def relative(root, path):
    return path.resolve().relative_to(root.resolve()).as_posix()


def local_path(root, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError("Expected repository-relative installation-local path")
    path = (root / value).resolve()
    if not path.is_relative_to((root / LOCAL_DIRECTORY).resolve()):
        raise ValueError("Record points outside installation-local storage")
    return path


def run_command(command, root, log, input_text=None):
    print("Preparing: " + " ".join(map(str, command)), flush=True)
    captured = []
    failures = []
    output_lock = threading.Lock()
    with log.open("x", encoding="utf-8") as stream:
        with subprocess.Popen(
            list(map(str, command)), cwd=root,
            stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        ) as process:
            def drain(pipe, capture):
                try:
                    for chunk in pipe:
                        if capture:
                            captured.append(chunk)
                        with output_lock:
                            try:
                                stream.write(chunk)
                                stream.flush()
                                print(chunk, end="", flush=True)
                            except (OSError, UnicodeError, ValueError) as error:
                                if not failures:
                                    failures.append(error)
                except (OSError, ValueError) as error:
                    failures.append(error)
                finally:
                    pipe.close()

            readers = [threading.Thread(target=drain, args=(process.stdout, True)),
                       threading.Thread(target=drain, args=(process.stderr, False))]
            for reader in readers:
                reader.start()
            try:
                if process.stdin is not None:
                    with suppress(BrokenPipeError):
                        process.stdin.write(input_text)
                    with suppress(BrokenPipeError):
                        process.stdin.close()
                returncode = process.wait()
            except BaseException:
                process.kill()
                process.wait()
                raise
            finally:
                for reader in readers:
                    reader.join()
    if returncode:
        raise RuntimeError(f"Preparation exited {returncode}; see {log}")
    if failures:
        raise RuntimeError(f"Preparation output could not be streamed; see {log}") from failures[0]
    return "".join(captured)


def ensure_runner(root, engine):
    expected = root / "dependency-migration/.venv-runner/Scripts/python.exe"
    if Path(sys.executable).resolve() != expected.resolve():
        raise RuntimeError(f"Invoke this helper with the existing locked runner: {expected}")
    fingerprint = engine.runner_fingerprint()
    if fingerprint["python"] != sys.version:
        raise RuntimeError("Runner fingerprint does not match this interpreter")
    return fingerprint


def validate_installation_profile(engine, path):
    profile = read_json(path)
    if not isinstance(profile, dict) or profile.get("qualified") is not False:
        raise ValueError(f"Installation profiles must remain unqualified; preserved {path}")
    key = None
    previous = None
    try:
        if profile.get("provider") in ("openai", "anthropic"):
            variable = profile["api_key_env"]
            if not isinstance(variable, str) or not variable or "=" in variable or "\0" in variable:
                raise ValueError("Invalid API key environment variable name")
            if not os.environ.get(variable):
                key = variable
                previous = os.environ.get(key)
                os.environ[key] = "offline-profile-validation"
        engine.validate_profile(profile, scored=False, allow_cloud=True)
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError(f"Invalid installation profile {path}: {error}") from error
    finally:
        if key is not None:
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


def prepare_profiles(root, engine):
    profiles = []
    for template in TEMPLATES:
        destination = root / LOCAL_DIRECTORY / "profiles" / (Path(template).stem + ".private.json")
        if not destination.exists():
            profile = read_json(root / "dependency-migration/profiles" / template)
            profile["qualified"] = False
            profile["label"] = "INSTALLATION-LOCAL " + Path(template).stem
            write_new(destination, profile)
        validate_installation_profile(engine, destination)
        profiles.append(relative(root, destination))
    return profiles


def verify_freeze(engine, path, hashes, image):
    frozen = read_json(path)
    if frozen.get("hashes") != hashes or frozen.get("python") != sys.version:
        raise RuntimeError("Installation freeze source/Python drift; use --refresh for a new generation")
    if frozen.get("image") != image or engine.image_id(image) != image:
        raise RuntimeError("Installation freeze image is missing or changed")


def verify_manifest(root, engine, manifest, runner):
    if (manifest.get("schema_version") != 1
            or manifest.get("scope") != "INSTALLATION-LOCAL"
            or manifest.get("qualified") is not False
            or manifest.get("repository_root") != str(root)
            or manifest.get("runner") != runner
            or set(manifest.get("workflows", {})) != set(WORKFLOWS)):
        raise RuntimeError("Installation manifest identity/runner drift; use --refresh")
    for name in WORKFLOWS:
        engine.configure_package(root / name)
        record = manifest["workflows"][name]
        freeze = local_path(root, record["freeze"])
        if engine.digest(freeze) != record["freeze_sha256"]:
            raise RuntimeError("Installation freeze bytes changed")
        verify_freeze(engine, freeze, engine.package_hashes(), record["image"])
        if record["deadline_seconds"] != read_json(root / name / "policy.json")["deadline_seconds"]:
            raise RuntimeError("Installation deadline changed")
        if set(record["images"]) != ({"v1", "v2"} if name == WORKFLOWS[0] else {"task"}):
            raise RuntimeError("Incomplete installation image record")
        if record["images"]["v2" if name == WORKFLOWS[0] else "task"] != record["image"]:
            raise RuntimeError("Installation task image mapping changed")
        for image in record["images"].values():
            if engine.image_id(image) != image:
                raise RuntimeError("Installation image changed")
        evidence = local_path(root, record["qualification"])
        if engine.digest(evidence) != record["qualification_sha256"]:
            raise RuntimeError("Qualification evidence changed")
        qualification = read_json(evidence)
        source = root / qualification["source"]
        if (not source.resolve().is_relative_to((root / name / "artifacts").resolve())
                or engine.digest(source) != qualification["source_sha256"]):
            raise RuntimeError("Original qualification evidence changed")
        if "smoke" not in record or "smoke_sha256" not in record:
            raise RuntimeError("Installation manifest lacks required smoke evidence; use --refresh")
        smoke = local_path(root, record["smoke"])
        if engine.digest(smoke) != record["smoke_sha256"]:
            raise RuntimeError("Smoke evidence changed; use --refresh")
        verify_smoke(root, engine, name, freeze, smoke, runner)
        expected_profiles = [relative(root, root / LOCAL_DIRECTORY / "profiles" /
                            (Path(template).stem + ".private.json")) for template in TEMPLATES]
        if record["profiles"] != expected_profiles:
            raise RuntimeError("Installation profile mapping changed")
        for value in record["profiles"]:
            validate_installation_profile(engine, local_path(root, value))


def verify_smoke(root, engine, name, freeze, receipt, runner):
    evidence = read_json(receipt)
    source = (root / evidence["source"]).resolve()
    artifacts = (root / name / "artifacts").resolve()
    if (Path(evidence["source"]).is_absolute() or source.parent.parent != artifacts
            or not source.parent.name.startswith("attempt-") or source.name != "result.json"
            or engine.digest(source) != evidence["source_sha256"]):
        raise RuntimeError("Original smoke result changed or escaped workflow artifacts; use --refresh")
    result = read_json(source)
    frozen = read_json(freeze)
    task_hash = hashlib.sha256(json.dumps(
        {"files": frozen["hashes"], "image": frozen["image"], "runner": runner},
        sort_keys=True).encode()).hexdigest()
    if (evidence.get("exit_code") != 0 or result.get("accepted") is not True
            or result.get("mock") is not True or result.get("scored") is not False
            or result.get("provider") != "mock" or result.get("model_calls") != 0
            or result.get("completed_model_calls") != 0
            or result.get("image") != frozen["image"] or result.get("runner") != runner
            or result.get("task_hash") != task_hash):
        raise RuntimeError("Smoke must be accepted, offline, unscored, and match this freeze/runner; use --refresh")


def smoke_workflow(root, engine, name, freeze, generation, runner):
    command = [sys.executable, root / name / "bench.py", "smoke", "--freeze", freeze]
    output = run_command(command, root, generation / f"{name}-smoke.log")
    locations = [line.removeprefix("Artifacts: ").strip() for line in output.splitlines()
                 if line.startswith("Artifacts: ")]
    if len(locations) != 1:
        raise RuntimeError("Smoke did not report exactly one artifacts directory")
    source = Path(locations[0]) / "result.json"
    if not source.is_absolute():
        source = root / source
    receipt = generation / f"{name}-smoke.json"
    write_new(receipt, {"source": relative(root, source), "source_sha256": engine.digest(source),
                        "command": list(map(str, command)), "exit_code": 0})
    verify_smoke(root, engine, name, freeze, receipt, runner)
    return receipt


def build_images(root, engine, name, generation):
    package = root / name
    variants = ("v1", "v2") if name == WORKFLOWS[0] else ("task",)
    images = {}
    for variant in variants:
        tag = f"ai-pc-installation-local/{name}:{generation.name}-{variant}"
        command = ["docker", "build", "--tag", tag]
        dockerfile = None
        context = package
        if variant == "v1":
            dockerfile = (package / "Dockerfile").read_text(encoding="utf-8")
            if dockerfile.count("requirements-v2.lock") != 3:
                raise RuntimeError("Migration Dockerfile changed; cannot derive the pinned v1 image")
            dockerfile = dockerfile.replace("requirements-v2.lock", "requirements-v1.lock")
            command += ["--file", "-"]
            context = generation / "migration-v1-context"
            context.mkdir()
            shutil.copyfile(package / "requirements-v1.lock", context / "requirements-v1.lock")
        command.append(context)
        run_command(command, root, generation / f"{name}-{variant}-build.log", dockerfile)
        images[variant] = engine.image_id(tag)
    return images


def qualify_workflow(root, engine, name, image, generation):
    script = root / name / "qualify.py"
    if name == WORKFLOWS[0]:
        run_command([sys.executable, script, "prepare"], root, generation / f"{name}-prepare.log")
    command = [sys.executable, script, "check"]
    if name != WORKFLOWS[0]:
        command += ["--image", image]
    output = run_command(command, root, generation / f"{name}-qualification.log")
    locations = [line.removeprefix("Evidence: ").strip() for line in output.splitlines()
                 if line.startswith("Evidence: ")]
    if len(locations) != 1:
        raise RuntimeError("Qualification did not report exactly one evidence directory")
    source = Path(locations[0]) / "qualification.json"
    if not source.is_absolute():
        source = root / source
    if not source.resolve().is_relative_to((root / name / "artifacts").resolve()):
        raise RuntimeError("Qualification evidence escaped workflow artifacts")
    if not read_json(source):
        raise RuntimeError("Qualification evidence is empty")
    receipt = generation / f"{name}-qualification.json"
    write_new(receipt, {"source": relative(root, source), "source_sha256": engine.digest(source),
                        "command": list(map(str, command)), "exit_code": 0})
    return receipt


def preparation_lock(local):
    return FileLock(local / ".prepare.lock", timeout=0)


def prepare(root, refresh=False, verify_only=False):
    if refresh and verify_only:
        raise ValueError("--refresh and --verify-only are mutually exclusive")
    root = Path(root).resolve()
    engine = load_engine(root)
    runner = ensure_runner(root, engine)
    local = root / LOCAL_DIRECTORY
    manifest_path = local / "workflows.json"
    if verify_only:
        if not manifest_path.is_file():
            raise RuntimeError("Installation manifest is missing; run preparation without --verify-only")
        verify_manifest(root, engine, read_json(manifest_path), runner)
        print(f"Verified INSTALLATION-LOCAL manifest: {manifest_path}", flush=True)
        return manifest_path
    local.mkdir(parents=True, exist_ok=True)
    with preparation_lock(local):
        if manifest_path.exists() and not refresh:
            verify_manifest(root, engine, read_json(manifest_path), runner)
            print(f"Verified INSTALLATION-LOCAL manifest: {manifest_path}", flush=True)
            return manifest_path
        generation = local / ("generation-" + uuid.uuid4().hex)
        generation.mkdir()
        profiles = prepare_profiles(root, engine)
        manifest = {"schema_version": 1, "scope": "INSTALLATION-LOCAL", "qualified": False,
                    "repository_root": str(root), "created_at": datetime.now(timezone.utc).isoformat(),
                    "runner": runner, "workflows": {}}
        for name in WORKFLOWS:
            engine.configure_package(root / name)
            hashes = engine.package_hashes()
            images = build_images(root, engine, name, generation)
            image = images["v2" if name == WORKFLOWS[0] else "task"]
            evidence = qualify_workflow(root, engine, name, image, generation)
            freeze = generation / f"{name}-INSTALLATION-LOCAL.json"
            run_command([sys.executable, root / name / "bench.py", "freeze", "--image", image,
                         "--output", freeze], root, generation / f"{name}-freeze.log")
            verify_freeze(engine, freeze, hashes, image)
            smoke = smoke_workflow(root, engine, name, freeze, generation, runner)
            if engine.package_hashes() != hashes or engine.runner_fingerprint() != runner:
                raise RuntimeError("Source or runner changed during preparation")
            manifest["workflows"][name] = {
                "freeze": relative(root, freeze), "freeze_sha256": engine.digest(freeze),
                "image": image, "images": images, "profiles": profiles,
                "qualification": relative(root, evidence), "qualification_sha256": engine.digest(evidence),
                "smoke": relative(root, smoke), "smoke_sha256": engine.digest(smoke),
                "deadline_seconds": read_json(root / name / "policy.json")["deadline_seconds"],
            }
        verify_manifest(root, engine, manifest, runner)
        staged = generation / "workflows.json"
        write_new(staged, manifest)
        temporary = local / (".manifest-" + uuid.uuid4().hex + ".tmp")
        try:
            write_new(temporary, manifest)
            os.replace(temporary, manifest_path)
        finally:
            temporary.unlink(missing_ok=True)
        print(f"Prepared INSTALLATION-LOCAL manifest: {manifest_path}", flush=True)
        return manifest_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--refresh", action="store_true", help="Retain history and prepare a new local generation")
    mode.add_argument("--verify-only", action="store_true", help="Verify an existing manifest without creating anything")
    args = parser.parse_args(argv)
    try:
        prepare(args.root, args.refresh, verify_only=args.verify_only)
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
        print(f"Blocked: {error}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
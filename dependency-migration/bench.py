"""Prepare, freeze, run, and summarize the dependency-migration experiment."""

import argparse
import ast
import base64
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import multiprocessing
import os
from pathlib import Path
import shlex
import shutil
import statistics
import subprocess
import sys
import time
from urllib.parse import urlsplit
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
ALLOWED = ("app/schemas.py", "app/settings.py", "app/routes.py", "tests/test_generated.py")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2), encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def package_hashes():
    paths = [path for directory in ("starter", "reference", "grader") for path in (ROOT / directory).rglob("*") if path.is_file() and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts]
    paths += [ROOT / name for name in ("bench.py", "worker.py", "qualify.py", "policy.json", "Dockerfile", "requirements-v1.lock", "requirements-v2.lock", "requirements-runner.lock")]
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(paths)}


def docker(*arguments, timeout=60, check=True):
    return subprocess.run(["docker", *map(str, arguments)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=check)


def image_id(image):
    if shutil.which("docker") is None:
        raise RuntimeError("Docker is missing. Install/start Docker Desktop with Linux containers; no host-execution fallback is allowed.")
    return docker("image", "inspect", "--format", "{{.Id}}", image).stdout.strip()


def runner_fingerprint():
    from packaging.requirements import Requirement

    if sys.version_info[:2] != (3, 11):
        raise RuntimeError("Use the locked Python 3.11 runner environment")
    versions = {}
    for line in (ROOT / "requirements-runner.lock").read_text(encoding="utf-8").splitlines():
        if not line or line[0].isspace() or line.startswith("#"):
            continue
        requirement = Requirement(line.rstrip("\\ "))
        if requirement.marker and not requirement.marker.evaluate():
            continue
        installed = importlib.metadata.version(requirement.name)
        if installed not in requirement.specifier:
            raise RuntimeError(f"Runner dependency drift: {requirement.name}")
        versions[requirement.name] = installed
    return {"python": sys.version, "packages": versions}


def cleanup_container(name):
    try:
        completed = docker("rm", "-f", name, check=False)
        return None if completed.returncode == 0 else "docker_remove_failed"
    except (OSError, subprocess.SubprocessError) as error:
        return type(error).__name__


def cleanup_task_volume(name):
    try:
        completed = docker("volume", "rm", name + "-task", check=False)
        return None if completed.returncode == 0 else "docker_volume_remove_failed"
    except (OSError, subprocess.SubprocessError) as error:
        return type(error).__name__


def validate_profile(profile, scored, allow_cloud):
    permitted = {"label", "provider", "base_url", "api_key_env", "model", "expected_returned_model", "extra_body", "qualified", "host", "inference", "rate_card"}
    if set(profile) - permitted:
        raise ValueError("Unknown profile keys; do not put credentials in profiles")
    provider = profile["provider"]
    endpoint = urlsplit(profile["base_url"])
    if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ValueError("Endpoint must not contain credentials, query, or fragment")
    if provider == "local":
        if endpoint.hostname != "127.0.0.1" or endpoint.scheme != "http":
            raise ValueError("Local inference must use an explicit http://127.0.0.1 loopback endpoint")
    elif provider == "anthropic":
        if profile["base_url"] != "https://api.anthropic.com" or not allow_cloud:
            raise ValueError("Cloud requires the fixed Anthropic endpoint and --allow-cloud")
        if not os.environ.get(profile["api_key_env"]):
            raise ValueError("Set the named API key environment variable outside chat; do not put the key in a file")
    else:
        raise ValueError("Only local and anthropic providers are supported")
    if set(profile["extra_body"]) - {"chat_template_kwargs"}:
        raise ValueError("extra_body may only configure chat_template_kwargs")
    if scored:
        if not profile["qualified"] or "REQUIRED" in json.dumps(profile) or "PIN EXACT" in json.dumps(profile):
            raise ValueError("Complete the profile and qualify the model/host before scored runs")
        context_limit = profile["inference"]["context_limit"]
        if not isinstance(context_limit, int) or isinstance(context_limit, bool) or context_limit <= 0:
            raise ValueError("Record and verify the model context limit before scored runs")
        if provider == "local" and any(profile["inference"][key] is None for key in ("cold_start_seconds", "peak_memory_gb")):
            raise ValueError("Local memory and cold-start measurements are required")
        if provider == "anthropic":
            card = profile["rate_card"]
            for key in ("input_per_million", "output_per_million", "cache_read_per_million", "cache_write_5m_per_million", "cache_write_1h_per_million"):
                if not isinstance(card[key], (int, float)) or card[key] < 0:
                    raise ValueError("Complete the saved provider rate card")


def collect_submission(exported, destination):
    destination.mkdir()
    violations = []
    for path in exported.rglob("*"):
        relative = path.relative_to(exported).as_posix()
        if path.is_symlink():
            violations.append(f"symlink: {relative}")
        elif path.is_file():
            if relative in ALLOWED:
                if path.stat().st_size > 128000:
                    violations.append(f"oversized: {relative}")
                else:
                    target = destination / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
            elif "__pycache__" not in path.parts and ".pytest_cache" not in path.parts:
                baseline = ROOT / "starter" / relative
                if not baseline.is_file() or digest(path) != digest(baseline):
                    violations.append(f"unpermitted change: {relative}")
    for baseline in (ROOT / "starter").rglob("*"):
        if baseline.is_file() and "__pycache__" not in baseline.parts and ".pytest_cache" not in baseline.parts:
            relative = baseline.relative_to(ROOT / "starter").as_posix()
            if relative not in ALLOWED and not (exported / relative).is_file():
                violations.append(f"deleted: {baseline.name}")
    return violations


def junit_passed(path):
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    return bool(cases) and not any(case.find(tag) is not None for case in cases for tag in ("failure", "error", "skipped"))


def junit_summary(path):
    cases = []
    for case in ET.parse(path).getroot().iter("testcase"):
        status = next((status for tag, status in (("error", "errors"), ("failure", "failed"), ("skipped", "skipped")) if case.find(tag) is not None), "passed")
        cases.append({"name": case.get("name", "unknown"), "classname": case.get("classname", ""), "status": status})
    return {"total": len(cases), **{status: sum(case["status"] == status for case in cases) for status in ("passed", "failed", "errors", "skipped")}, "cases": cases}


def has_test_assertion(tree):
    for test_function in (node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test")):
        pending = list(test_function.body)
        while pending:
            node = pending.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, ast.Assert) and not isinstance(node.test, ast.Constant):
                return True
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "raises" or node.func.attr.startswith("assert"):
                    return True
            pending.extend(ast.iter_child_nodes(node))
    return False


def verify(submission, output, image, policy):
    regression_issue = None
    try:
        tree = ast.parse((submission / "tests/test_generated.py").read_text(encoding="utf-8"))
        if not has_test_assertion(tree):
            regression_issue = "missing_regression_assertions"
    except FileNotFoundError:
        regression_issue = "missing_test_file"
    except (SyntaxError, UnicodeError):
        regression_issue = "invalid_test_source"
    results = {}
    test_results = {}
    phase_errors = {}
    cleanup_errors = []
    failed_tests = []
    for phase in ("contract", "generated"):
        if phase == "generated" and regression_issue == "missing_test_file":
            results[phase] = False
            test_results[phase] = {"total": 0, "passed": 0, "failed": 0, "errors": 1, "skipped": 0, "cases": []}
            phase_errors[phase] = "MissingGeneratedTestFile"
            continue
        name = "migration-verifier-" + uuid.uuid4().hex[:12]
        try:
            docker("run", "-d", "--name", name, "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "128", "--cpus", policy["container_cpus"], "--memory", policy["container_memory"], "--tmpfs", "/tmp:rw,nosuid,size=128m", "--mount", f"type=bind,src={submission.resolve()},dst=/task,readonly", "--mount", f"type=bind,src={ROOT / 'grader'},dst=/grader,readonly", image, "tail", "-f", "/dev/null")
            tests = ["/grader/test_contract.py", "/grader/test_native.py"] if phase == "contract" else ["/task/tests/test_generated.py"]
            completed = docker("exec", name, "python", "-W", "error::pydantic.PydanticDeprecatedSince20", "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider", "--import-mode=importlib", "--noconftest", "--junitxml=/tmp/report.xml", timeout=policy["verifier_timeout_seconds"], check=False)
            (output / f"{phase}.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
            report = output / f"{phase}.xml"
            copied = docker("exec", name, "cat", "/tmp/report.xml", check=False)
            if copied.returncode == 0:
                report.write_text(copied.stdout, encoding="utf-8")
                test_results[phase] = junit_summary(report)
            results[phase] = completed.returncode == 0 and copied.returncode == 0 and junit_passed(report)
            if copied.returncode == 0 and not results[phase]:
                failed_tests.extend(case.get("name", "unknown") for case in ET.parse(report).getroot().iter("testcase") if any(case.find(tag) is not None for tag in ("failure", "error", "skipped")))
        except (subprocess.SubprocessError, ET.ParseError) as error:
            results[phase] = False
            phase_errors[phase] = type(error).__name__
        finally:
            cleanup_error = cleanup_container(name)
            if cleanup_error:
                cleanup_errors.append({"container": name, "error": cleanup_error})
    if regression_issue:
        results["generated"] = False
    accepted = all(results.values())
    return {"accepted": accepted, "category": "accepted" if accepted else regression_issue or "verification_failed", "checks": results, "test_results": test_results, "phase_errors": phase_errors, "regression_issue": regression_issue, "failed_tests": failed_tests, "cleanup_errors": cleanup_errors}


def check_submission(container, output, image, policy):
    output.mkdir()
    docker("pause", container)
    accepted = False
    try:
        exported = output / "exported"
        exported.mkdir()
        docker("cp", container + ":/task/.", exported)
        violations = collect_submission(exported, output / "submission")
        try:
            verification_started = time.perf_counter()
            review = verify(output / "submission", output, image, policy)
            review["verifier_seconds"] = time.perf_counter() - verification_started
        except (SyntaxError, UnicodeError) as error:
            return {"accepted": False, "category": "invalid_test_source", "error_type": type(error).__name__}
        if review.get("cleanup_errors"):
            raise RuntimeError("Verifier cleanup failed; resolve containers before continuing")
        review["violations"] = violations
        accepted = review["accepted"] and not violations
        if violations:
            review.update(accepted=False, category="submission_policy_violation")
        return review
    finally:
        if not accepted:
            docker("unpause", container)


def read_events(output):
    path = output / "events.jsonl"
    events = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def api_fee(profile, events):
    if profile["provider"] in ("local", "mock"):
        return 0.0
    responses = [event for event in events if event["kind"] == "request_end"]
    if len(responses) != sum(event["kind"] == "request_start" for event in events):
        return None
    card = profile["rate_card"]
    total = 0.0
    for response in responses:
        usage = response["usage"]
        if not usage or "input_tokens" not in usage or "output_tokens" not in usage:
            return None
        creation = usage.get("cache_creation") or {}
        short = creation.get("ephemeral_5m_input_tokens", 0)
        long = creation.get("ephemeral_1h_input_tokens", 0)
        if (usage.get("cache_creation_input_tokens") or 0) != short + long:
            return None
        categories = [(usage["input_tokens"], "input_per_million"), (usage["output_tokens"], "output_per_million"), (usage.get("cache_read_input_tokens") or 0, "cache_read_per_million"), (short, "cache_write_5m_per_million"), (long, "cache_write_1h_per_million")]
        for tokens, key in categories:
            if card.get(key) is None:
                return None
            total += tokens * card[key] / 1000000
    return total


def observed_span_seconds(events, prefix, cutoff):
    pending = None
    total = 0.0
    for event in events:
        if event["kind"] == prefix + "_start":
            pending = event["at"]
        elif event["kind"] in (prefix + "_end", prefix + "_error") and pending is not None:
            total += max(0, min(cutoff, event["at"]) - pending)
            pending = None
    if pending is not None:
        total += max(0, cutoff - pending)
    return total


def usage_metrics(events):
    responses = [event for event in events if event["kind"] == "request_end"]
    totals = {}

    def accumulate(values, prefix=""):
        for key, value in values.items():
            name = prefix + key
            if isinstance(value, dict):
                accumulate(value, name + ".")
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[name] = totals.get(name, 0) + value

    for response in responses:
        accumulate(response.get("usage") or {})
    seconds = sum(response.get("seconds", 0) for response in responses)
    output_tokens = sum((response.get("usage") or {}).get("completion_tokens", (response.get("usage") or {}).get("output_tokens", 0)) for response in responses)
    known = all(response.get("usage") is not None for response in responses)
    return {"native_usage_totals": totals, "usage_complete": known and len(responses) == sum(event["kind"] == "request_start" for event in events), "completed_model_calls": len(responses), "completed_request_output_tokens_per_second": output_tokens / seconds if known and seconds else None}


def wait_for_worker(connection, started, deadline_seconds, on_submission):
    while True:
        if deadline_seconds is None:
            message = connection.recv()
        else:
            remaining = max(0, deadline_seconds - (time.perf_counter() - started))
            if remaining == 0:
                return {"kind": "deadline", "at": started + deadline_seconds}
            message = connection.recv() if connection.poll(remaining) else {"kind": "deadline", "at": started + deadline_seconds}
        if message["kind"] != "submission_check":
            return message
        review = on_submission()
        feedback = {key: review[key] for key in ("category", "checks", "failed_tests", "violations", "error_type") if key in review}
        connection.send({"accepted": review["accepted"], "feedback": json.dumps(feedback)})


def run_attempt(profile, frozen, scored, mock=False):
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    active = artifacts / "active-run.json"
    try:
        with active.open("x", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid()}, stream)
    except FileExistsError:
        raise RuntimeError("An active-run lock exists. Do not overlap attempts; check the recorded PID before removing a stale lock.") from None
    try:
        return _run_attempt(profile, frozen, scored, mock)
    finally:
        active.unlink(missing_ok=True)


def _run_attempt(profile, frozen, scored, mock=False):
    from worker import run_worker

    image = image_id(frozen["image"])
    runner = runner_fingerprint()
    if frozen["hashes"] != package_hashes():
        raise ValueError("Package changed since freeze; recalibrate and create a new freeze")
    policy = load(ROOT / "policy.json")
    task_hash = hashlib.sha256(json.dumps({"files": frozen["hashes"], "image": image, "runner": runner}, sort_keys=True).encode()).hexdigest()
    if scored:
        smoke_results = [load(path) for path in (ROOT / "artifacts").glob("attempt-*/result.json")]
        if not any(record.get("mock") and record.get("accepted") and record.get("task_hash") == task_hash for record in smoke_results):
            raise RuntimeError("Run an accepted offline Docker smoke test for this exact package/image/runner before scoring")
    output = ROOT / "artifacts" / ("attempt-" + uuid.uuid4().hex)
    output.mkdir(parents=True)
    prepared = output / "prepared"
    shutil.copytree(ROOT / "starter", prepared, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    name = "migration-agent-" + uuid.uuid4().hex[:12]
    save(output / "profile.json", {key: value for key, value in profile.items() if key != "mock_commands"})
    save(output / "freeze.json", frozen)
    result = {"attempt_id": output.name, "created_at": datetime.now(timezone.utc).isoformat(), "label": profile["label"], "scored": scored, "mock": mock, "image": image, "runner": runner, "task_hash": task_hash, "profile_hash": hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest(), "accepted": False, "category": "preparation_error", "agent_seconds": None, "verifier_seconds": 0, "api_fee_usd": None}
    result.update(provider=profile["provider"], model=profile.get("model"), submission_checks=0, rejected_submissions=0, submission_check_seconds=0.0, execution_mode="until_verified" if policy["deadline_seconds"] is None else "deadline", deadline_seconds=policy["deadline_seconds"])
    last_review = None
    last_checkpoint = None

    def on_submission():
        from worker import append_event

        nonlocal last_review, last_checkpoint
        result["submission_checks"] += 1
        checkpoint = output / f"check-{result['submission_checks']:03}"
        print(f"Checking submission {result['submission_checks']}...", flush=True)
        check_started = time.perf_counter()
        append_event(output / "events.jsonl", {"kind": "validation_start", "at": check_started})
        try:
            review = check_submission(name, checkpoint, image, policy)
            last_review, last_checkpoint = review, checkpoint
            save(checkpoint / "review.json", review)
            result["rejected_submissions"] += int(not review["accepted"])
            result["verifier_seconds"] += review.get("verifier_seconds", 0)
            print("Verified completion." if review["accepted"] else f"Rejected: {review['category']}; agent will continue repairing.", flush=True)
            return review
        finally:
            result["submission_check_seconds"] += time.perf_counter() - check_started
            append_event(output / "events.jsonl", {"kind": "validation_end", "at": time.perf_counter()})

    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=run_worker, args=(child, profile, policy, image, name, str(prepared), str(output)))
    started = None
    try:
        process.start()
        child.close()
        if not parent.poll(120) or parent.recv()["kind"] != "ready":
            raise RuntimeError("Worker preparation failed; inspect prerequisites")
        parent.send("start")
        if not parent.poll(10):
            raise RuntimeError("Worker did not acknowledge task handoff")
        started = parent.recv()["at"]
        if policy["deadline_seconds"] is not None:
            print(f"Agent work budget: {policy['deadline_seconds']} seconds. Evaluation follows after work stops.", flush=True)
        finished = wait_for_worker(parent, started, policy["deadline_seconds"], on_submission)
        elapsed = finished["at"] - started
        result.update(submission_seconds=elapsed, category=finished["kind"], worker_outcome=finished)
        if not last_review or not last_review["accepted"]:
            docker("pause", name)
        result["agent_seconds"] = time.perf_counter() - started
        result["cutoff_overrun_seconds"] = max(0, result["agent_seconds"] - policy["deadline_seconds"]) if policy["deadline_seconds"] is not None else None
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        result["exit_status"] = finished.get("result", {}).get("exit_status", finished["kind"])
        submitted = result["exit_status"] == "Submitted"
        print("Agent stopped. Evaluating saved files...", flush=True)
        exported = output / "exported"
        if last_review and last_review["accepted"]:
            shutil.copytree(last_checkpoint / "exported", exported)
            shutil.copytree(last_checkpoint / "submission", output / "submission")
            violations = []
        else:
            exported.mkdir()
            docker("cp", name + ":/task/.", exported)
            violations = collect_submission(exported, output / "submission")
        result["submission_violations"] = violations
        if last_review and last_review["accepted"]:
            verification = last_review
            for filename in ("contract.txt", "contract.xml", "generated.txt", "generated.xml"):
                source = last_checkpoint / filename
                if source.exists():
                    shutil.copyfile(source, output / filename)
        else:
            verification_start = time.perf_counter()
            verification = verify(output / "submission", output, image, policy)
            result["verifier_seconds"] += time.perf_counter() - verification_start
        result["through_verification_seconds"] = time.perf_counter() - started
        result["verification"] = verification
        result["accepted"] = verification["accepted"] and not violations
        if violations:
            result["category"] = "submission_policy_violation"
        else:
            result["category"] = verification["category"] if submitted or result["accepted"] else result["exit_status"]
    except (Exception, KeyboardInterrupt) as error:
        result["category"] = type(error).__name__
        if started is not None and result["agent_seconds"] is None:
            result["agent_seconds"] = time.perf_counter() - started
    finally:
        if process.pid is not None and process.is_alive():
            process.terminate()
        if process.pid is not None:
            process.join(timeout=5)
        parent.close()
        child.close()
        result["cleanup_error"] = cleanup_container(name)
        result["volume_cleanup_error"] = cleanup_task_volume(name)
        events = read_events(output)
        result.update(usage_metrics(events))
        result["model_calls"] = sum(event["kind"] == "request_start" for event in events)
        cutoff = started + result["agent_seconds"] if started is not None and result["agent_seconds"] is not None else time.perf_counter()
        result["request_seconds"] = observed_span_seconds(events, "request", cutoff)
        result["tool_seconds"] = max(0, observed_span_seconds(events, "tool", cutoff) - observed_span_seconds(events, "validation", cutoff))
        result["incomplete_request_count"] = result["model_calls"] - sum(event["kind"] == "request_end" for event in events)
        result["request_fraction"] = result["request_seconds"] / result["agent_seconds"] if result["agent_seconds"] else None
        result["tool_calls"] = sum(event["kind"] == "tool_start" for event in events)
        result["failed_tool_calls"] = sum(event["kind"] == "tool_result" and event["returncode"] != 0 for event in events)
        result["api_fee_usd"] = api_fee(profile, events)
        result["accepted_within_budget"] = result["accepted"] and (policy["deadline_seconds"] is None or result["submission_seconds"] <= policy["deadline_seconds"])
        result.setdefault("through_verification_seconds", None)
        result["completion_seconds"] = result["through_verification_seconds"] if result["accepted"] else None
        result["through_cleanup_seconds"] = time.perf_counter() - started if started is not None else None
        save(output / "result.json", result)
    print(json.dumps(result, indent=2))
    print(f"Artifacts: {output}")
    return 0 if result["accepted"] else 1


def report(directory):
    groups = {}
    for path in Path(directory).glob("attempt-*/result.json"):
        result = load(path)
        key = (result["task_hash"], result["profile_hash"], result["scored"], result["mock"])
        groups.setdefault(key, []).append(result)
    rows = []
    for attempts in groups.values():
        accepted = [attempt for attempt in attempts if attempt["accepted"]]
        times = [attempt["agent_seconds"] for attempt in accepted]
        early_successes = [attempt["submission_seconds"] for attempt in accepted if attempt.get("exit_status") == "Submitted" and attempt.get("submission_seconds") is not None]
        fees = [attempt["api_fee_usd"] for attempt in attempts]
        total = sum(fees) if all(fee is not None for fee in fees) else None
        rows.append({"label": attempts[0]["label"], "task_hash": attempts[0]["task_hash"], "profile_hash": attempts[0]["profile_hash"], "scored": attempts[0]["scored"], "mock": attempts[0]["mock"], "attempts": len(attempts), "accepted": len(accepted), "accepted_within_budget": sum(attempt["accepted_within_budget"] for attempt in attempts) if all("accepted_within_budget" in attempt for attempt in attempts) else None, "median_success_seconds": statistics.median(times) if times else None, "success_range_seconds": [min(times), max(times)] if times else None, "median_early_success_seconds": statistics.median(early_successes) if early_successes else None, "early_success_range_seconds": [min(early_successes), max(early_successes)] if early_successes else None, "total_api_fee_usd": total, "api_fee_per_accepted_usd": total / len(accepted) if accepted and total is not None else None, "failures": [attempt["category"] for attempt in attempts if not attempt["accepted"]], "nonstandard_stops": [{"attempt_id": attempt.get("attempt_id"), "stop_reason": attempt["exit_status"], "error_type": attempt.get("worker_outcome", {}).get("error_type")} for attempt in attempts if attempt.get("exit_status") is not None and attempt["exit_status"] not in ("Submitted", "deadline")]})
        row = rows[-1]
        native_totals = {}
        for attempt in attempts:
            for key, value in attempt.get("native_usage_totals", {}).items():
                native_totals[key] = native_totals.get(key, 0) + value
        completion_times = [attempt["completion_seconds"] for attempt in accepted if attempt.get("completion_seconds") is not None]
        row.update(provider=attempts[0].get("provider"), model=attempts[0].get("model"), execution_mode=attempts[0].get("execution_mode", "legacy_deadline"), deadline_seconds=attempts[0].get("deadline_seconds"), acceptance_rate=len(accepted) / len(attempts), median_completion_seconds=statistics.median(completion_times) if completion_times else None, native_usage_totals=native_totals, usage_complete=all(attempt.get("usage_complete", False) for attempt in attempts), cleanup_failures=sum(bool(attempt.get("cleanup_error") or attempt.get("volume_cleanup_error") or attempt.get("verification", {}).get("cleanup_errors")) for attempt in attempts), contract_passes=sum(attempt.get("verification", {}).get("checks", {}).get("contract", False) for attempt in attempts), generated_test_passes=sum(attempt.get("verification", {}).get("checks", {}).get("generated", False) for attempt in attempts))
        row["evaluation_results"] = [{"attempt_id": attempt.get("attempt_id"), "stop_reason": attempt.get("exit_status", attempt["category"]), "test_results": attempt.get("verification", {}).get("test_results", {}), "regression_issue": attempt.get("verification", {}).get("regression_issue"), "phase_errors": attempt.get("verification", {}).get("phase_errors", {}), "submission_violations": attempt.get("submission_violations", [])} for attempt in attempts]
        for metric in ("model_calls", "tool_calls", "failed_tool_calls", "rejected_submissions", "submission_checks", "incomplete_request_count", "request_seconds", "tool_seconds", "verifier_seconds", "submission_check_seconds"):
            values = [attempt.get(metric) for attempt in attempts]
            row["total_" + metric] = sum(values) if all(value is not None for value in values) else None
    print(json.dumps(rows, indent=2))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--image", default="migration-task:0.1")
    freeze.add_argument("--output", type=Path, default=ROOT / "artifacts/freeze-240s-v3.json")
    for name in ("run", "smoke"):
        command = commands.add_parser(name)
        command.add_argument("--freeze", type=Path, default=ROOT / "artifacts/freeze-240s-v3.json")
        if name == "smoke":
            command.add_argument("--deadline-probe", action="store_true", help="Write partial repairs then simulate an unresponsive model until the frozen deadline")
        if name == "run":
            command.add_argument("--profile", type=Path, required=True)
            command.add_argument("--scored", action="store_true")
            command.add_argument("--allow-cloud", action="store_true")
    summary = commands.add_parser("report")
    summary.add_argument("--directory", type=Path, default=ROOT / "artifacts")
    args = parser.parse_args()
    if args.command == "freeze":
        if args.output.exists():
            raise ValueError("Freeze already exists; use a new --output path to retain history")
        frozen = {"created_at": datetime.now(timezone.utc).isoformat(), "image": image_id(args.image), "hashes": package_hashes(), "python": sys.version}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        save(args.output, frozen)
        print(f"Frozen: {args.output}. A freeze is not evidence of calibration.")
    elif args.command == "report":
        report(args.directory)
    elif args.command == "run":
        profile = load(args.profile)
        validate_profile(profile, args.scored, args.allow_cloud)
        return run_attempt(profile, load(args.freeze), args.scored)
    else:
        files = {relative: (ROOT / "reference" / relative).read_text(encoding="utf-8") for relative in ALLOWED}
        if args.deadline_probe:
            if load(ROOT / "policy.json")["deadline_seconds"] is None:
                raise ValueError("Deadline probe requires a finite frozen policy")
            files.pop("tests/test_generated.py")
        encoded = base64.b64encode(json.dumps(files).encode()).decode()
        script = "import base64,json,pathlib; files=json.loads(base64.b64decode('" + encoded + "')); [pathlib.Path(name).write_text(text) for name,text in files.items()]"
        commands = ["cat TASK.md", "python -c " + shlex.quote(script)]
        if not args.deadline_probe:
            commands += ["python -m pytest -q -p no:cacheprovider", "printf 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\\nsmoke\\n'"]
        profile = {"label": "offline-deadline-probe" if args.deadline_probe else "offline-harness-smoke", "provider": "mock", "model": "offline-mock", "mock_commands": commands, "mock_wait_after_commands": args.deadline_probe}
        return run_attempt(profile, load(args.freeze), False, mock=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, subprocess.SubprocessError, FileNotFoundError) as error:
        print(f"Blocked: {error}", file=sys.stderr)
        sys.exit(2)
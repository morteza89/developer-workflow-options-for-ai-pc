import json
from pathlib import Path
import shutil
import subprocess

import pytest

import bench
import comparison_report
import qualify


@pytest.mark.parametrize("existing", [False, True])
def test_prepare_creates_only_missing_environments_and_always_syncs(tmp_path, monkeypatch, existing):
    monkeypatch.setattr(qualify, "ROOT", tmp_path)
    commands = []
    for version in ("v1", "v2"):
        if existing:
            executable = qualify.interpreter(version)
            executable.parent.mkdir(parents=True)
            executable.touch()
            (tmp_path / f".venv-{version}" / "pyvenv.cfg").touch()

    def execute(command):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(qualify, "execute", execute)
    qualify.prepare()
    assert sum(command[:2] == ["uv", "venv"] for command in commands) == (0 if existing else 2)
    syncs = [command for command in commands if command[:3] == ["uv", "pip", "sync"]]
    assert len(syncs) == 2
    assert all("--require-hashes" in command for command in syncs)
    assert sum("-c" in command for command in commands) == (2 if existing else 0)


@pytest.mark.parametrize("complete", [False, True])
def test_prepare_preserves_invalid_existing_environment(tmp_path, monkeypatch, complete):
    monkeypatch.setattr(qualify, "ROOT", tmp_path)
    directory = tmp_path / ".venv-v1"
    directory.mkdir()
    sentinel = directory / "keep.txt"
    sentinel.write_text("preserve me", encoding="utf-8")
    if complete:
        executable = qualify.interpreter("v1")
        executable.parent.mkdir(parents=True)
        executable.touch()
        (directory / "pyvenv.cfg").touch()

    def execute(command):
        assert "-c" in command
        return subprocess.CompletedProcess(command, 1, "", "invalid interpreter")

    monkeypatch.setattr(qualify, "execute", execute)
    with pytest.raises(RuntimeError, match="Move it aside"):
        qualify.prepare()
    assert sentinel.read_text(encoding="utf-8") == "preserve me"


def test_local_route_cannot_silently_become_cloud():
    profile = bench.load(bench.ROOT / "profiles/local-8b.json")
    bench.validate_profile(profile, False, False)
    for url in ("https://example.com/v1", "http://localhost:8000/v1", "http://secret@127.0.0.1:8000/v1"):
        profile["base_url"] = url
        with pytest.raises(ValueError):
            bench.validate_profile(profile, False, False)


def test_unqualified_profile_cannot_be_scored():
    with pytest.raises(ValueError, match="qualify"):
        bench.validate_profile(bench.load(bench.ROOT / "profiles/local-8b.json"), True, False)


def test_scored_profile_requires_measured_context_limit():
    profile = bench.load(bench.ROOT / "profiles/local-8b.json")
    profile["qualified"] = True
    profile["host"].update(sku="test host", os="test OS", driver="test driver", bios="test BIOS", power_mode="Best performance")
    profile["inference"].update(runtime="OVMS", runtime_sha256="sha", model_revision="rev", export_sha256="sha", template_sha256="sha", cache_policy="warm", cold_start_seconds=1, peak_memory_gb=10, offload_evidence="measured", no_cloud_fallback_evidence="loopback")
    with pytest.raises(ValueError, match="context limit"):
        bench.validate_profile(profile, True, False)


def test_cloud_requires_opt_in_and_environment_secret(monkeypatch):
    profile = bench.load(bench.ROOT / "profiles/claude.json")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="allow-cloud"):
        bench.validate_profile(profile, False, False)
    with pytest.raises(ValueError, match="environment"):
        bench.validate_profile(profile, False, True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-not-a-credential")
    bench.validate_profile(profile, False, True)


def test_openai_requires_opt_in_and_environment_secret(monkeypatch):
    profile = bench.load(bench.ROOT / "profiles/openai.json")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="allow-cloud"):
        bench.validate_profile(profile, False, False)
    with pytest.raises(ValueError, match="environment"):
        bench.validate_profile(profile, False, True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-credential")
    bench.validate_profile(profile, False, True)


def test_openai_responses_request_uses_fixed_model_and_shared_budget():
    from types import SimpleNamespace
    from worker import openai_finish_reason, openai_response_input, openai_response_options

    profile = bench.load(bench.ROOT / "profiles/openai.json")
    policy = bench.load(bench.ROOT / "policy.json")
    messages = [
        {"role": "system", "content": "instructions"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": "answer", "tool_calls": None, "function_call": None},
    ]
    options = openai_response_options(profile, policy, messages)
    assert options["model"] == "gpt-6.1-sol"
    assert options["instructions"] == "instructions"
    assert options["input"] == [{"role": "user", "content": "task"}, {"role": "assistant", "content": "answer"}]
    assert openai_response_input(messages) == options["input"]
    assert options["max_output_tokens"] == 2048
    assert options["reasoning"] == {"effort": "medium"}
    assert options["timeout"] == 600
    assert openai_finish_reason(SimpleNamespace(status="completed")) == "stop"
    assert openai_finish_reason(SimpleNamespace(status="incomplete", incomplete_details=SimpleNamespace(reason="max_output_tokens"))) == "length"


def test_openai_multiple_action_blocks_execute_only_first():
    from worker import normalize_openai_action

    response = """```mswea_bash_command
printf 'first'
```
```mswea_bash_command
printf 'second'
```"""
    normalized, count = normalize_openai_action(response)
    assert count == 2
    assert normalized == "```mswea_bash_command\nprintf 'first'\n```"
    assert "second" not in normalized


def test_openai_action_normalization_leaves_single_and_nonaction_text_unchanged():
    from worker import normalize_openai_action

    single = "```mswea_bash_command\nprintf 'one'\n```"
    assert normalize_openai_action(single) == (single, 1)
    assert normalize_openai_action("no action") == ("no action", 0)


def test_provider_error_diagnostics_keep_status_and_redact_key():
    from types import SimpleNamespace
    from worker import request_error_details

    error = SimpleNamespace(status_code=400, code="bad_request", param="input", request_id="req_test", message="invalid key sk-proj-123456789012345678901234")
    details = request_error_details(error)
    assert details["status_code"] == 400
    assert details["code"] == "bad_request"
    assert details["param"] == "input"
    assert "sk-proj-123456789012345678901234" not in details["message"]


def test_openai_fee_accounts_for_cached_reads_writes_and_long_context():
    profile = bench.load(bench.ROOT / "profiles/openai.json")
    card = profile["rate_card"]
    events = [
        {"kind": "request_start"},
        {"kind": "request_end", "usage": {"input_tokens": 1000, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 100, "cache_write_tokens": 400}}},
    ]
    assert bench.api_fee(profile, events) == pytest.approx(0.00221)
    long_events = [
        {"kind": "request_start"},
        {"kind": "request_end", "usage": {"input_tokens": card["long_context_threshold_tokens"] + 1, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}}},
    ]
    expected = (card["long_context_threshold_tokens"] + 1) * 4 / 1_000_000 + 20 * 15 / 1_000_000
    assert bench.api_fee(profile, long_events) == pytest.approx(expected)


def test_submission_filter_keeps_only_permitted_files(tmp_path):
    exported = tmp_path / "exported"
    shutil.copytree(bench.ROOT / "starter", exported, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    for relative in bench.ALLOWED:
        shutil.copyfile(bench.ROOT / "reference" / relative, exported / relative)
    destination = tmp_path / "submission"
    assert bench.collect_submission(exported, destination) == []
    assert sorted(path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()) == sorted(bench.ALLOWED)


def test_submission_filter_preserves_partial_allowed_files_and_reports_extra_files(tmp_path):
    exported = tmp_path / "exported"
    shutil.copytree(bench.ROOT / "starter", exported)
    for relative in bench.ALLOWED:
        (exported / relative).unlink(missing_ok=True)
    (exported / "app").mkdir(exist_ok=True)
    (exported / "app/schemas.py").write_text("partial", encoding="utf-8")
    (exported / "log.txt").write_text("unexpected", encoding="utf-8")
    destination = tmp_path / "submission"
    violations = bench.collect_submission(exported, destination)
    assert (destination / "app/schemas.py").read_text(encoding="utf-8") == "partial"
    assert sorted(violations) == ["unpermitted change: log.txt"]


@pytest.mark.parametrize("filename", ["TASK.md", "tests/test_visible.py", "conftest.py", "requirements.txt"])
def test_submission_rejects_unpermitted_edits(tmp_path, filename):
    exported = tmp_path / "exported"
    shutil.copytree(bench.ROOT / "starter", exported)
    (exported / filename).write_text("tampered", encoding="utf-8")
    assert any("unpermitted" in problem for problem in bench.collect_submission(exported, tmp_path / "submission"))


@pytest.mark.parametrize("xml,accepted", [("<testsuites/>", False), ('<testsuites><testsuite><testcase name="ok"/></testsuite></testsuites>', True), ('<testsuites><testsuite><testcase name="skip"><skipped/></testcase></testsuite></testsuites>', False), ('<testsuites><testsuite><testcase name="fail"><failure/></testcase></testsuite></testsuites>', False)])
def test_junit_requires_executed_passing_tests(tmp_path, xml, accepted):
    path = tmp_path / "report.xml"
    path.write_text(xml, encoding="utf-8")
    assert bench.junit_passed(path) is accepted


def test_junit_summary_retains_named_partial_results(tmp_path):
    path = tmp_path / "report.xml"
    path.write_text('<testsuites><testsuite><testcase name="ok"/><testcase name="bad"><failure/></testcase><testcase name="collection"><error/></testcase><testcase name="skip"><skipped/></testcase></testsuite></testsuites>', encoding="utf-8")
    summary = bench.junit_summary(path)
    assert {key: value for key, value in summary.items() if key != "cases"} == {"total": 4, "passed": 1, "failed": 1, "errors": 1, "skipped": 1}
    assert summary["cases"][0] == {"name": "ok", "classname": "", "status": "passed"}


@pytest.mark.parametrize("source,expected", [
    ("def test_contract():\n    assert response.status_code == 201", True),
    ("def test_rejects_invalid():\n    with pytest.raises(ValueError):\n        parse('bad')", True),
    ("class TestContract:\n    def test_response(self):\n        self.assertEqual(actual, expected)", True),
    ("def helper():\n    assert response.status_code == 201", False),
    ("def test_placeholder():\n    assert True", False),
    ("def test_placeholder():\n    pass", False),
])
def test_generated_test_assertion_detection(source, expected):
    assert bench.has_test_assertion(bench.ast.parse(source)) is expected


def test_truncated_model_response_is_explained_to_agent():
    from minisweagent.exceptions import FormatError
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel
    import litellm

    policy = bench.load(bench.ROOT / "policy.json")
    model = LitellmTextbasedModel(model_name="offline", format_error_template=policy["format_error_template"])
    response = litellm.ModelResponse(model="offline", choices=[{"message": {"role": "assistant", "content": "partial"}, "finish_reason": "length"}])
    with pytest.raises(FormatError) as error:
        model._parse_actions(response)
    assert "truncated at the output limit" in error.value.messages[0]["content"]


@pytest.mark.parametrize("source,issue", [("", "missing_regression_assertions"), ("def broken(", "invalid_test_source"), (None, "missing_test_file")])
def test_verification_evaluates_contract_despite_missing_or_broken_tests(tmp_path, monkeypatch, source, issue):
    submission = tmp_path / "submission"
    (submission / "tests").mkdir(parents=True)
    if source is not None:
        (submission / "tests/test_generated.py").write_text(source, encoding="utf-8")
    phases = []

    def fake_docker(*arguments, **kwargs):
        if "pytest" in arguments:
            phases.append("contract" if "/grader/test_contract.py" in arguments else "generated")
        text = '<testsuites><testsuite><testcase name="health"/><testcase name="receipt"><failure/></testcase></testsuite></testsuites>'
        return subprocess.CompletedProcess(arguments, 0, text, "")

    monkeypatch.setattr(bench, "docker", fake_docker)
    result = bench.verify(submission, tmp_path, "image", {"container_cpus": 2, "container_memory": "2g", "verifier_timeout_seconds": 60})
    assert phases == (["contract"] if source is None else ["contract", "generated"])
    assert not result["accepted"]
    assert result["category"] == issue
    assert result["test_results"]["contract"]["passed"] == 1
    assert result["test_results"]["contract"]["failed"] == 1
    if source is None:
        assert result["phase_errors"]["generated"] == "MissingGeneratedTestFile"


def test_submission_policy_violation_retains_protected_results(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "docker", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "", ""))
    monkeypatch.setattr(bench, "collect_submission", lambda *args: ["unpermitted change: log.txt"])
    monkeypatch.setattr(bench, "verify", lambda *args: {"accepted": True, "category": "accepted", "test_results": {"contract": {"passed": 38}}})
    result = bench.check_submission("task", tmp_path / "checkpoint", "image", {})
    assert not result["accepted"]
    assert result["category"] == "submission_policy_violation"
    assert result["violations"] == ["unpermitted change: log.txt"]
    assert result["test_results"]["contract"]["passed"] == 38


def test_cloud_fee_counts_cache_categories_and_incomplete_calls():
    profile = {"provider": "anthropic", "rate_card": {"input_per_million": 3, "output_per_million": 15, "cache_read_per_million": 0.3, "cache_write_5m_per_million": 3.75, "cache_write_1h_per_million": 6}}
    usage = {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 50, "cache_creation_input_tokens": 30, "cache_creation": {"ephemeral_5m_input_tokens": 20, "ephemeral_1h_input_tokens": 10}}
    events = [{"kind": "request_start"}, {"kind": "request_end", "usage": usage}]
    assert bench.api_fee(profile, events) == pytest.approx(0.00075)
    assert bench.api_fee(profile, events + [{"kind": "request_start"}]) is None
    usage["cache_creation_input_tokens"] = 40
    assert bench.api_fee(profile, events) is None
    assert bench.api_fee({"provider": "local"}, []) == 0


def test_cleanup_errors_are_recordable(monkeypatch):
    def failing_docker(*args, **kwargs):
        raise subprocess.TimeoutExpired("docker", 60)

    monkeypatch.setattr(bench, "docker", failing_docker)
    assert bench.cleanup_container("test") == "TimeoutExpired"


def test_no_success_has_undefined_cost_per_acceptance(tmp_path):
    output = tmp_path / "attempt-one"
    output.mkdir()
    bench.save(output / "result.json", {"task_hash": "task", "profile_hash": "profile", "label": "test", "scored": True, "mock": False, "accepted": False, "api_fee_usd": 0, "category": "deadline"})
    row = bench.report(tmp_path)[0]
    assert row["attempts"] == 1
    assert row["api_fee_per_accepted_usd"] is None
    assert row["accepted_within_budget"] is None


def test_saved_profiles_and_agent_frontmatter():
    import yaml

    for path in (bench.ROOT / "profiles").glob("*.json"):
        profile = bench.load(path)
        assert "api_key" not in profile
    content = (bench.ROOT.parent / ".github/agents/workflow-author.agent.md").read_text(encoding="utf-8")
    header = yaml.safe_load(content.split("---", 2)[1])
    assert header["description"]
    assert "model" not in header


@pytest.mark.parametrize("preliminary_steps", [0, 25])
def test_pinned_mini_agent_text_loop(tmp_path, monkeypatch, preliminary_steps):
    monkeypatch.setenv("MSWEA_GLOBAL_CONFIG_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT", "1")
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.docker import DockerEnvironment
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel
    import litellm

    class OfflineModel(LitellmTextbasedModel):
        calls = 0

        def _query(self, messages, **kwargs):
            self.calls += 1
            if self.calls <= preliminary_steps:
                return litellm.ModelResponse(choices=[{"message": {"role": "assistant", "content": "```mswea_bash_command\nprintf 'progress\\n'\n```"}, "finish_reason": "stop"}])
            return litellm.ModelResponse(choices=[{"message": {"role": "assistant", "content": "```mswea_bash_command\nprintf 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\\nchecked\\n'\n```"}, "finish_reason": "stop"}])

        def _calculate_cost(self, response):
            return {"cost": 0.0}

    class OfflineEnvironment(DockerEnvironment):
        def _start_container(self):
            self.container_id = None

        def execute(self, action, **kwargs):
            assert action["command"].startswith("printf")
            if "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" not in action["command"]:
                return {"output": "progress", "returncode": 0, "exception_info": ""}
            self._check_finished({"output": "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\nchecked\n", "returncode": 0})

    policy = bench.load(bench.ROOT / "policy.json")
    agent = DefaultAgent(OfflineModel(model_name="offline", cost_tracking="ignore_errors"), OfflineEnvironment(image="unused"), system_template=policy["system_template"], instance_template=policy["instance_template"], step_limit=policy["step_limit"], cost_limit=0)
    assert agent.run("check the loop")["exit_status"] == "Submitted"
    assert agent.n_calls == preliminary_steps + 1


def test_actual_runner_matches_lock():
    assert bench.runner_fingerprint()["packages"]["mini-swe-agent"] == "2.4.6"


def test_interrupted_request_span_is_counted_once():
    events = [{"kind": "request_start", "at": 10}, {"kind": "request_end", "at": 20}, {"kind": "request_error", "at": 21}, {"kind": "request_start", "at": 30}]
    assert bench.observed_span_seconds(events, "request", 35) == 15


@pytest.mark.parametrize("deadline,unlimited,worker_error", [(False, False, False), (False, False, True), (True, False, False), (False, True, False)])
def test_supervisor_stops_worker_before_verification_and_retains_cleanup_error(tmp_path, monkeypatch, deadline, unlimited, worker_error):
    real_root = bench.ROOT
    shutil.copytree(real_root / "starter", tmp_path / "starter")
    policy = bench.load(real_root / "policy.json")
    policy["deadline_seconds"] = None if unlimited else 600
    bench.save(tmp_path / "policy.json", policy)
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    monkeypatch.setattr(bench, "image_id", lambda image: "sha256:test")
    monkeypatch.setattr(bench, "runner_fingerprint", lambda: {"python": "test"})
    monkeypatch.setattr(bench, "package_hashes", lambda: {})
    monkeypatch.setattr(bench.time, "perf_counter", lambda: 805 if unlimited else (705 if deadline else 150))
    actions = []

    class Pipe:
        messages = iter([{"kind": "ready"}, {"kind": "started", "at": 100}, {"kind": "error", "at": 140, "error_type": "RuntimeError"} if worker_error else {"kind": "finished", "at": 800 if unlimited else 140, "result": {"exit_status": "Submitted"}}])
        polls = 0

        def poll(self, timeout):
            self.polls += 1
            return not (deadline and self.polls == 3)

        def recv(self):
            return next(self.messages)

        def send(self, message):
            pass

        def close(self):
            pass

    class Process:
        pid = 1
        alive = True

        def start(self):
            pass

        def is_alive(self):
            return self.alive

        def terminate(self):
            actions.append("terminate")
            self.alive = False

        def join(self, timeout):
            pass

    class Context:
        def Pipe(self):
            return Pipe(), Pipe()

        def Process(self, **kwargs):
            return Process()

    def fake_docker(*arguments, **kwargs):
        if arguments[0] == "pause":
            actions.append("pause")
        elif arguments[0] == "cp":
            exported = Path(arguments[2])
            shutil.copytree(real_root / "starter", exported, dirs_exist_ok=True)
            for relative in bench.ALLOWED:
                shutil.copyfile(real_root / "reference" / relative, exported / relative)
        elif arguments[0] == "rm":
            raise subprocess.TimeoutExpired("docker", 60)
        elif arguments[0] == "volume":
            return subprocess.CompletedProcess(arguments, 0)

    def fake_verify(*args):
        actions.append("verify")
        return {"accepted": True, "category": "accepted"}

    monkeypatch.setattr(bench.multiprocessing, "get_context", lambda mode: Context())
    monkeypatch.setattr(bench, "docker", fake_docker)
    monkeypatch.setattr(bench, "verify", fake_verify)
    result_code = bench.run_attempt({"label": "unit", "provider": "local"}, {"image": "test", "hashes": {}}, False)
    result = bench.load(next((tmp_path / "artifacts").glob("attempt-*/result.json")))
    assert actions[:3] == ["pause", "terminate", "verify"]
    assert result["cleanup_error"] == "TimeoutExpired"
    assert result["accepted"]
    assert result["accepted_within_budget"]
    assert result_code == 0
    if deadline:
        assert result["exit_status"] == "deadline"
        assert result["verification"]["accepted"]
    if worker_error:
        assert result["exit_status"] == "error"
        assert result["accepted"]


def test_ten_minute_policy_and_after_work_evaluation():
    from worker import render_system_template, request_options

    policy = bench.load(bench.ROOT / "policy.json")
    assert policy["deadline_seconds"] == 600
    assert policy["step_limit"] == 0
    assert policy["max_conversation_characters"] is None
    assert "reference_range_seconds" not in policy
    assert "success_cutoff_seconds" not in policy
    assert "600 seconds total" in render_system_template(policy)
    assert "stops at 600 seconds" in render_system_template(policy)
    assert "truncated at the output limit" in policy["format_error_template"]
    task = (bench.ROOT / "starter/TASK.md").read_text(encoding="utf-8")
    assert "600 seconds" in task
    assert "Their results are not returned for further repairs" in task
    for filename in ("local-8b.json", "article-27b.json", "claude.json", "openai.json"):
        assert request_options(bench.load(bench.ROOT / "profiles" / filename), policy)["timeout"] == 600


def test_deadline_does_not_accept_buffered_messages_after_cutoff(monkeypatch):
    monkeypatch.setattr(bench.time, "perf_counter", lambda: 701)

    class Connection:
        def poll(self, timeout):
            pytest.fail("Do not receive another action after the deadline")

    assert bench.wait_for_worker(Connection(), 100, 600, lambda: pytest.fail("No in-loop verification")) == {"kind": "deadline", "at": 700}


def test_unlimited_supervisor_returns_rejection_then_acceptance_feedback():
    class Connection:
        messages = iter([{"kind": "submission_check"}, {"kind": "submission_check"}, {"kind": "finished", "at": 10000}])
        replies = []

        def poll(self, timeout):
            pytest.fail("Unlimited task must not poll a deadline")

        def recv(self):
            return next(self.messages)

        def send(self, message):
            self.replies.append(message)

    reviews = iter([{"accepted": False, "category": "missing_regression_assertions"}, {"accepted": True, "category": "accepted"}])
    connection = Connection()
    assert bench.wait_for_worker(connection, 100, None, lambda: next(reviews))["at"] == 10000
    assert [reply["accepted"] for reply in connection.replies] == [False, True]


@pytest.mark.parametrize("accepted", [False, True])
def test_worker_only_finishes_verified_submission(accepted):
    from worker import review_submission

    class Connection:
        def send(self, message):
            assert message["kind"] == "submission_check"

        def recv(self):
            return {"accepted": accepted, "feedback": "missing_regression_assertions"}

    output = {"returncode": 0, "output": "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\ndone\n"}
    review_submission(output, Connection())
    assert output["returncode"] == (0 if accepted else 1)
    assert output["output"].startswith("COMPLETE_TASK") is accepted


@pytest.mark.parametrize("accepted", [False, True])
def test_submission_snapshot_stays_paused_only_when_accepted(tmp_path, monkeypatch, accepted):
    actions = []

    def fake_docker(*arguments, **kwargs):
        actions.append(arguments[0])

    monkeypatch.setattr(bench, "docker", fake_docker)
    monkeypatch.setattr(bench, "collect_submission", lambda *args: [])
    monkeypatch.setattr(bench, "verify", lambda *args: {"accepted": accepted, "category": "accepted" if accepted else "verification_failed"})
    review = bench.check_submission("test", tmp_path / "check", "image", {})
    assert review["accepted"] is accepted
    assert actions == (["pause", "cp"] if accepted else ["pause", "cp", "unpause"])


def test_native_usage_totals_keep_provider_fields_and_unknown_calls():
    events = [{"kind": "request_start"}, {"kind": "request_end", "seconds": 10, "usage": {"input_tokens": 100, "output_tokens": 20, "cache_creation": {"ephemeral_5m_input_tokens": 4}}}]
    metrics = bench.usage_metrics(events)
    assert metrics["native_usage_totals"]["cache_creation.ephemeral_5m_input_tokens"] == 4
    assert metrics["completed_request_output_tokens_per_second"] == 2
    assert metrics["usage_complete"]
    assert not bench.usage_metrics(events + [{"kind": "request_start"}])["usage_complete"]


def test_usage_report_counts_normalized_openai_action_blocks():
    events = [
        {"kind": "request_start"},
        {"kind": "request_end", "seconds": 1, "usage": {"input_tokens": 100, "output_tokens": 10}, "normalized_action_blocks": 3},
    ]
    metrics = bench.usage_metrics(events)
    assert metrics["normalized_action_response_count"] == 1
    assert metrics["discarded_action_block_count"] == 2


def test_completion_report_keeps_slow_success_and_profiles_separate(tmp_path):
    for index, profile in enumerate(("local8", "local27", "cloud")):
        output = tmp_path / f"attempt-{index}"
        output.mkdir()
        exit_status = ("Submitted", "deadline", "error")[index]
        record = {"attempt_id": output.name, "task_hash": "completion-task", "profile_hash": profile, "label": profile, "scored": False, "mock": False, "accepted": True, "agent_seconds": 900, "completion_seconds": 902, "api_fee_usd": 0 if index < 2 else 0.5, "category": "accepted", "exit_status": exit_status, "submission_seconds": (12, 600, 200)[index], "native_usage_totals": {"output_tokens": 200}, "usage_complete": True, "verification": {"checks": {"contract": True, "generated": True}}}
        if index == 2:
            record["worker_outcome"] = {"error_type": "RuntimeError"}
        bench.save(output / "result.json", record)
    rows = bench.report(tmp_path)
    assert len(rows) == 3
    assert all(row["acceptance_rate"] == 1 for row in rows)
    assert all(row["median_completion_seconds"] == 902 for row in rows)
    assert all(row["contract_passes"] == row["generated_test_passes"] == 1 for row in rows)
    assert [row["median_early_success_seconds"] for row in rows] == [12, None, None]
    assert rows[2]["nonstandard_stops"][0]["error_type"] == "RuntimeError"


def test_report_retains_partial_deadline_evaluation(tmp_path):
    output = tmp_path / "attempt-partial"
    output.mkdir()
    summary = {"contract": {"total": 2, "passed": 1, "failed": 1, "errors": 0, "skipped": 0, "cases": [{"name": "health", "status": "passed"}, {"name": "receipt", "status": "failed"}]}}
    bench.save(output / "result.json", {"attempt_id": output.name, "task_hash": "ten-minute", "profile_hash": "local27", "label": "local27", "scored": False, "mock": False, "accepted": False, "accepted_within_budget": False, "deadline_seconds": 600, "api_fee_usd": 0, "category": "deadline", "exit_status": "deadline", "verification": {"test_results": summary, "regression_issue": "missing_regression_assertions"}})
    row = bench.report(tmp_path)[0]
    assert row["accepted"] == 0
    assert row["evaluation_results"][0]["stop_reason"] == "deadline"
    assert row["evaluation_results"][0]["test_results"] == summary
    assert row["evaluation_results"][0]["regression_issue"] == "missing_regression_assertions"
    assert row["deadline_seconds"] == 600
    assert row["accepted_within_budget"] == 0


def test_comparison_report_filters_freeze_and_summarizes_models(tmp_path):
    frozen = {"created_at": "current", "image": "sha256:current", "hashes": {"task": "current"}}
    records = [
        ("27b", "local", "qwen3.8-27b-ov", True, 0, 39, 39, 6.5),
        ("8b", "local", "OpenVINO/Qwen3-8B-int8-ov", False, 0, 39, 0, None),
        ("openai", "openai", "gpt-6.1-sol", True, 0.25, 39, 27, 34.0),
    ]
    for name, provider, model, accepted, api_fee, contract_passed, generated_passed, output_rate in records:
        attempt = tmp_path / f"attempt-{name}"
        attempt.mkdir()
        bench.save(attempt / "freeze.json", frozen)
        bench.save(attempt / "result.json", {
            "attempt_id": attempt.name,
            "label": name,
            "provider": provider,
            "model": model,
            "task_hash": "current-task",
            "profile_hash": f"{name}-profile",
            "scored": False,
            "mock": False,
            "accepted": accepted,
            "category": "accepted" if accepted else "test_failure",
            "exit_status": "Submitted" if accepted else "deadline",
            "agent_seconds": 30,
            "through_verification_seconds": 32,
            "api_fee_usd": api_fee,
            "completed_request_output_tokens_per_second": output_rate,
            "native_usage_totals": {"input_tokens": 1000, "output_tokens": 200},
            "verification": {"test_results": {
                "contract": {"passed": contract_passed, "total": 39},
                "generated": {"passed": generated_passed, "total": 27},
            }},
        })

    old = tmp_path / "attempt-old"
    old.mkdir()
    bench.save(old / "freeze.json", {"created_at": "old"})
    bench.save(old / "result.json", {
        "attempt_id": old.name,
        "label": "old",
        "provider": "local",
        "model": "older-model",
        "mock": False,
    })
    profile_paths = []
    for index, (name, provider, model, *_rest) in enumerate(records):
        path = tmp_path / f"profile-{index}.json"
        device = "provider-managed" if provider == "openai" else "GPU"
        bench.save(path, {
            "label": name,
            "provider": provider,
            "model": model,
            "inference": {"device": device, "runtime": "test-runtime"},
        })
        profile_paths.append(path)
    old_profile = tmp_path / "profile-old.json"
    bench.save(old_profile, {
        "label": "old model",
        "provider": "local",
        "model": "older-model",
    })
    profile_paths.append(old_profile)

    report = comparison_report.render_report(tmp_path, frozen, profile_paths)
    assert "Matching model attempts: 3; other saved attempts excluded: 1; matching mock attempts excluded: 0" in report
    assert "| 8b | local / OpenVINO/Qwen3-8B-int8-ov | GPU; test-runtime | 1 | 0 | ready |" in report
    assert "| openai | openai / gpt-6.1-sol | provider-managed; test-runtime | 1 | 0 | ready |" in report
    assert "| old model | local / older-model | unknown; unknown | 0 | 1 | RERUN (1 other freeze) |" in report
    assert "| openai | openai / gpt-6.1-sol | pilot | `current-task` | 1 | 1 | 1/1 (100%)" in report
    assert "| openai | openai / gpt-6.1-sol | pilot | `current-task` | 1 | 1 | 1/1 (100%) | 32.0s | 34.0 |" in report
    assert "| openai | `attempt-openai` | accepted | Submitted | 30.0s | 32.0s | 34.0 |" in report
    assert "| 8b | local / OpenVINO/Qwen3-8B-int8-ov | pilot | `current-task` | 1 | 0 | 0/1 (0%) | n/a | n/a |" in report
    assert "39/39" in report
    assert "0/27" in report
    assert "$0.2500" in report
    assert "`attempt-old`" not in report
    security_report = comparison_report.render_report(tmp_path, frozen, profile_paths, title="Security Repair Comparison")
    assert security_report.startswith("# Security Repair Comparison\n")
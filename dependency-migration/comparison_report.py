"""Create a human-readable comparison from attempts for one frozen task."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent
DEFAULT_PROFILES = (
    "profiles/ptl-morteza89-27b.private.json",
    "profiles/ptl-8b.private.json",
    "profiles/ptl-openai.private.json",
    "profiles/ptl-openai-astra.private.json",
    "profiles/ptl-qwen3-coder-30b.private.json",
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cell(value):
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def duration(value):
    return "n/a" if value is None else f"{value:.1f}s"


def fee(value):
    return "unknown" if value is None else f"${value:.4f}"


def throughput(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "n/a"
    return f"{value:.1f}"


def test_count(attempt, phase):
    summary = attempt.get("verification", {}).get("test_results", {}).get(phase)
    if not summary:
        return "n/a"
    return f"{summary.get('passed', 0)}/{summary.get('total', 0)}"


def test_total(attempts, phase):
    summaries = [
        attempt.get("verification", {}).get("test_results", {}).get(phase)
        for attempt in attempts
    ]
    summaries = [summary for summary in summaries if summary]
    if not summaries:
        return "n/a"
    passed = sum(summary.get("passed", 0) for summary in summaries)
    total = sum(summary.get("total", 0) for summary in summaries)
    suffix = f" ({len(summaries)}/{len(attempts)} evaluated)" if len(summaries) != len(attempts) else ""
    return f"{passed}/{total}{suffix}"


def matching_attempts(directory, frozen):
    result_paths = sorted(Path(directory).glob("attempt-*/result.json"))
    matched = []
    model_attempts = []
    mock_excluded = 0
    for result_path in result_paths:
        result = read_json(result_path)
        if not result.get("mock"):
            model_attempts.append(result)
        freeze_path = result_path.parent / "freeze.json"
        if freeze_path.is_file() and read_json(freeze_path) == frozen:
            if result.get("mock"):
                mock_excluded += 1
            else:
                matched.append(result)
    return matched, len(result_paths) - len(matched) - mock_excluded, mock_excluded, model_attempts


def render_report(directory, frozen, profile_paths=DEFAULT_PROFILES, title="Dependency Migration Comparison"):
    attempts, excluded, mock_excluded, model_attempts = matching_attempts(directory, frozen)
    lines = [
        f"# {title}",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Frozen task created: {frozen.get('created_at', 'unknown')}",
        f"Task image: `{frozen.get('image', 'unknown')}`",
        f"Matching model attempts: {len(attempts)}; other saved attempts excluded: {excluded}; matching mock attempts excluded: {mock_excluded}",
        "",
        "Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.",
        "",
        "## Model Coverage",
        "",
        "| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for profile_path in profile_paths:
        if not Path(profile_path).is_file():
            lines.append(f"| {cell(Path(profile_path).stem)} | not configured | not configured | 0 | 0 | PROFILE MISSING |")
            continue
        profile = read_json(profile_path)
        count = sum(
            attempt.get("provider") == profile.get("provider")
            and attempt.get("model") == profile.get("model")
            for attempt in attempts
        )
        all_count = sum(
            attempt.get("provider") == profile.get("provider")
            and attempt.get("model") == profile.get("model")
            for attempt in model_attempts
        )
        other_freeze_count = all_count - count
        status = "ready" if count else (f"RERUN ({other_freeze_count} other freeze)" if other_freeze_count else "MISSING")
        identity = f"{profile.get('provider', 'unknown')} / {profile.get('model', 'unknown')}"
        inference = profile.get("inference", {})
        device_runtime = f"{inference.get('device', 'unknown')}; {inference.get('runtime', 'unknown')}"
        lines.append(
            f"| {cell(profile.get('label', Path(profile_path).stem))} | {cell(identity)} | {cell(device_runtime)} | {count} | {other_freeze_count} | {status} |"
        )

    groups = {}
    for attempt in attempts:
        key = (
            attempt.get("label", "unknown"), attempt.get("provider", "unknown"),
            attempt.get("model", "unknown"), attempt.get("task_hash", "unknown"),
            attempt.get("profile_hash", "unknown"), attempt.get("scored", False),
            attempt.get("mock", False),
        )
        groups.setdefault(key, []).append(attempt)

    lines.extend([
        "",
        "## Summary",
        "",
        "| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for key, group in sorted(groups.items()):
        label, provider, model, task_hash, _, scored, mock = key
        accepted = [attempt for attempt in group if attempt.get("accepted")]
        times = [attempt.get("through_verification_seconds", attempt.get("agent_seconds")) for attempt in accepted]
        times = [value for value in times if value is not None]
        rates = [
            attempt["completed_request_output_tokens_per_second"]
            for attempt in group
            if isinstance(attempt.get("completed_request_output_tokens_per_second"), (int, float))
            and not isinstance(attempt.get("completed_request_output_tokens_per_second"), bool)
        ]
        median_rate = statistics.median(rates) if rates else None
        fees = [attempt.get("api_fee_usd") for attempt in group]
        total_fee = sum(fees) if all(value is not None for value in fees) else None
        run_type = "mock" if mock else ("scored" if scored else "pilot")
        acceptance = f"{len(accepted)}/{len(group)} ({len(accepted) / len(group):.0%})"
        median = duration(statistics.median(times) if times else None)
        identity = f"{provider} / {model}"
        lines.append(
            f"| {cell(label)} | {cell(identity)} | {run_type} | `{task_hash[:12]}` | {len(group)} | {len(accepted)} | {acceptance} | {median} | {throughput(median_rate)} | {test_total(group, 'contract')} | {test_total(group, 'generated')} | {fee(total_fee)} |"
        )

    lines.extend([
        "",
        "## Attempt Details",
        "",
        "| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for attempt in sorted(attempts, key=lambda item: item.get("created_at", "")):
        usage = attempt.get("native_usage_totals", {})
        tokens = f"{usage.get('input_tokens', 'n/a')} / {usage.get('output_tokens', 'n/a')}"
        outcome = "accepted" if attempt.get("accepted") else attempt.get("category", "failed")
        stop = attempt.get("exit_status", attempt.get("category", "unknown"))
        lines.append(
            f"| {cell(attempt.get('label', 'unknown'))} | `{cell(attempt.get('attempt_id', 'unknown'))}` | {cell(outcome)} | {cell(stop)} | {duration(attempt.get('agent_seconds'))} | {duration(attempt.get('through_verification_seconds'))} | {throughput(attempt.get('completed_request_output_tokens_per_second'))} | {test_count(attempt, 'contract')} | {test_count(attempt, 'generated')} | {fee(attempt.get('api_fee_usd'))} | {tokens} |"
        )
    fault_attempts = [attempt for attempt in attempts if attempt.get("verification", {}).get("faults_total", 0)]
    if fault_attempts:
        lines.extend([
            "", "## Fault Detection", "",
            "| Model | Attempt | Faults detected | Undetected faults | Evaluation errors |",
            "| --- | --- | ---: | --- | --- |",
        ])
        for attempt in fault_attempts:
            verification = attempt["verification"]
            undetected = [name.removeprefix("fault_") for name, passed in verification.get("checks", {}).items() if name.startswith("fault_") and not passed]
            errors = verification.get("phase_errors", {})
            lines.append(f"| {cell(attempt.get('label', 'unknown'))} | `{cell(attempt.get('attempt_id', 'unknown'))}` | {verification['faults_detected']}/{verification['faults_total']} | {cell(', '.join(undetected) or 'none')} | {cell(', '.join(errors) or 'none')} |")
        lines.extend(["", "Detection credit requires the same generated tests to pass on clean code and fail by ordinary assertions on each fault, without errors or skips. Raw failing-test counts alone are not detection credit."])
    lines.extend([
        "",
        "Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, action="append", default=[])
    parser.add_argument("--title", default="Dependency Migration Comparison")
    args = parser.parse_args()
    frozen = read_json(args.freeze)
    profiles = args.profile or [ROOT / path for path in DEFAULT_PROFILES]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(args.directory, frozen, profiles, args.title), encoding="utf-8")
    print(f"Comparison report written: {args.output}")


if __name__ == "__main__":
    main()
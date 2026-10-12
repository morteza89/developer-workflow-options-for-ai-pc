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
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cell(value):
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def duration(value):
    return "n/a" if value is None else f"{value:.1f}s"


def fee(value):
    return "unknown" if value is None else f"${value:.4f}"


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
    mock_excluded = 0
    for result_path in result_paths:
        freeze_path = result_path.parent / "freeze.json"
        if freeze_path.is_file() and read_json(freeze_path) == frozen:
            result = read_json(result_path)
            if result.get("mock"):
                mock_excluded += 1
            else:
                matched.append(result)
    return matched, len(result_paths) - len(matched) - mock_excluded, mock_excluded


def render_report(directory, frozen, profile_paths=DEFAULT_PROFILES):
    attempts, excluded, mock_excluded = matching_attempts(directory, frozen)
    lines = [
        "# Dependency Migration Comparison",
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
        "| Configured model | Provider / model ID | Device / runtime | Matching attempts | Status |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for profile_path in profile_paths:
        profile = read_json(profile_path)
        count = sum(
            attempt.get("provider") == profile.get("provider")
            and attempt.get("model") == profile.get("model")
            for attempt in attempts
        )
        identity = f"{profile.get('provider', 'unknown')} / {profile.get('model', 'unknown')}"
        inference = profile.get("inference", {})
        device_runtime = f"{inference.get('device', 'unknown')}; {inference.get('runtime', 'unknown')}"
        lines.append(
            f"| {cell(profile.get('label', Path(profile_path).stem))} | {cell(identity)} | {cell(device_runtime)} | {count} | {'ready' if count else 'MISSING'} |"
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
        "| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Contract tests | Generated tests | API fees |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for key, group in sorted(groups.items()):
        label, provider, model, task_hash, _, scored, mock = key
        accepted = [attempt for attempt in group if attempt.get("accepted")]
        times = [attempt.get("through_verification_seconds", attempt.get("agent_seconds")) for attempt in accepted]
        times = [value for value in times if value is not None]
        fees = [attempt.get("api_fee_usd") for attempt in group]
        total_fee = sum(fees) if all(value is not None for value in fees) else None
        run_type = "mock" if mock else ("scored" if scored else "pilot")
        acceptance = f"{len(accepted)}/{len(group)} ({len(accepted) / len(group):.0%})"
        median = duration(statistics.median(times) if times else None)
        identity = f"{provider} / {model}"
        lines.append(
            f"| {cell(label)} | {cell(identity)} | {run_type} | `{task_hash[:12]}` | {len(group)} | {len(accepted)} | {acceptance} | {median} | {test_total(group, 'contract')} | {test_total(group, 'generated')} | {fee(total_fee)} |"
        )

    lines.extend([
        "",
        "## Attempt Details",
        "",
        "| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Contract tests | Generated tests | API fee | Input / output tokens |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for attempt in sorted(attempts, key=lambda item: item.get("created_at", "")):
        usage = attempt.get("native_usage_totals", {})
        tokens = f"{usage.get('input_tokens', 'n/a')} / {usage.get('output_tokens', 'n/a')}"
        outcome = "accepted" if attempt.get("accepted") else attempt.get("category", "failed")
        stop = attempt.get("exit_status", attempt.get("category", "unknown"))
        lines.append(
            f"| {cell(attempt.get('label', 'unknown'))} | `{cell(attempt.get('attempt_id', 'unknown'))}` | {cell(outcome)} | {cell(stop)} | {duration(attempt.get('agent_seconds'))} | {duration(attempt.get('through_verification_seconds'))} | {test_count(attempt, 'contract')} | {test_count(attempt, 'generated')} | {fee(attempt.get('api_fee_usd'))} | {tokens} |"
        )
    lines.extend([
        "",
        "Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, action="append", default=[])
    args = parser.parse_args()
    frozen = read_json(args.freeze)
    profiles = args.profile or [ROOT / path for path in DEFAULT_PROFILES]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(args.directory, frozen, profiles), encoding="utf-8")
    print(f"Comparison report written: {args.output}")


if __name__ == "__main__":
    main()
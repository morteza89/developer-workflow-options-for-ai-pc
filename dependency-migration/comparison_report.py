"""Create a human-readable comparison from attempts for one frozen task."""

import argparse
from datetime import datetime, timezone
import hashlib
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
    "profiles/ptl-qwen38-fable5-coding-27b.private.json",
)


def read_json(path, strict=True):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if strict:
            raise
        return None


def profile_hash(profile):
    return hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()


def cell(value):
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def duration(value):
    return "n/a" if value is None else f"{value:.1f}s"


def fee(value, incomplete=False):
    if value is None:
        return "unknown"
    return f"\u2265 ${value:.4f} (incomplete)" if incomplete else f"${value:.4f}"


def first_present(mapping, *keys):
    for key in keys:
        if mapping.get(key) is not None:
            return mapping[key]
    return None


def token_cell(usage):
    usage = usage or {}
    input_tokens = first_present(usage, "input_tokens", "prompt_tokens")
    output_tokens = first_present(usage, "output_tokens", "completion_tokens")
    reasoning = first_present(usage, "output_tokens_details.reasoning_tokens", "completion_tokens_details.reasoning_tokens")
    text = f"{'n/a' if input_tokens is None else input_tokens} / {'n/a' if output_tokens is None else output_tokens}"
    return text if reasoning is None else f"{text} (reasoning {reasoning})"


def yes_no(value):
    return "n/a" if value is None else ("yes" if value else "no")


def setting(settings, key):
    value = settings.get(key)
    return "n/a" if value is None else ("yes" if value is True else "no" if value is False else value)


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
    skipped = 0
    for result_path in result_paths:
        result = read_json(result_path, strict=False)
        freeze_path = result_path.parent / "freeze.json"
        saved_freeze = read_json(freeze_path, strict=False) if freeze_path.is_file() else None
        if not isinstance(result, dict) or (freeze_path.is_file() and saved_freeze is None):
            skipped += 1
            continue
        if not result.get("mock"):
            model_attempts.append(result)
        if saved_freeze == frozen:
            if result.get("mock"):
                mock_excluded += 1
            else:
                matched.append(result)
    return matched, len(result_paths) - len(matched) - mock_excluded - skipped, mock_excluded, model_attempts, skipped


def profile_matches(attempt, profile):
    return attempt.get("provider") == profile.get("provider") and attempt.get("model") == profile.get("model")


def profile_current(attempt, current_hash):
    # Legacy attempts without a recorded profile_hash cannot be attributed and are kept as matching.
    return attempt.get("profile_hash") in (None, current_hash)


def render_report(directory, frozen, profile_paths=DEFAULT_PROFILES, title="Dependency Migration Comparison", freeze_name=None):
    attempts, excluded, mock_excluded, model_attempts, skipped = matching_attempts(directory, frozen)
    lines = [
        f"# {title}",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Freeze file: {freeze_name or 'unknown'}",
        f"Frozen task created: {frozen.get('created_at', 'unknown')}",
        f"Task image: `{frozen.get('image', 'unknown')}`",
        f"Matching model attempts: {len(attempts)}; other saved attempts excluded: {excluded}; matching mock attempts excluded: {mock_excluded}",
    ]
    if skipped:
        lines.append(f"Skipped malformed artifacts: {skipped}")
    lines.extend([
        "",
        "Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.",
        "",
        "## Model Coverage",
        "",
        "| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ])
    profiles = []
    for profile_path in profile_paths:
        if not Path(profile_path).is_file():
            lines.append(f"| {cell(Path(profile_path).stem)} | not configured | not configured | 0 | 0 | PROFILE MISSING |")
            continue
        profile = read_json(profile_path)
        current_hash = profile_hash(profile)
        profiles.append((profile_path, profile, current_hash))
        same_model = [attempt for attempt in attempts if profile_matches(attempt, profile)]
        count = sum(profile_current(attempt, current_hash) for attempt in same_model)
        stale_count = len(same_model) - count
        all_count = sum(profile_matches(attempt, profile) for attempt in model_attempts)
        other_freeze_count = all_count - len(same_model)
        if count:
            status = "ready"
        elif stale_count:
            status = "RERUN (profile changed)"
        elif other_freeze_count:
            status = f"RERUN ({other_freeze_count} other freeze)"
        else:
            status = "MISSING"
        identity = f"{profile.get('provider', 'unknown')} / {profile.get('model', 'unknown')}"
        inference = profile.get("inference", {})
        device_runtime = f"{inference.get('device', 'unknown')}; {inference.get('runtime', 'unknown')}"
        lines.append(
            f"| {cell(profile.get('label', Path(profile_path).stem))} | {cell(identity)} | {cell(device_runtime)} | {count} | {other_freeze_count} | {status} |"
        )

    settings_rows = []
    for profile_path, profile, _current_hash in profiles:
        same_model = [attempt for attempt in attempts if profile_matches(attempt, profile)]
        if not same_model:
            continue
        settings = same_model[0].get("request_settings") or {}
        settings_rows.append(
            f"| {cell(profile.get('label', Path(profile_path).stem))} | {cell(setting(settings, 'sampling'))} | {cell(setting(settings, 'temperature'))} | {cell(setting(settings, 'reasoning'))} | {cell(setting(settings, 'max_output_tokens'))} | {cell(setting(settings, 'output_cap_includes_reasoning_tokens'))} | {cell(setting(settings, 'api'))} |"
        )
    if settings_rows:
        lines.extend([
            "",
            "## Request Settings",
            "",
            "| Configured model | Sampling | Temperature | Reasoning | Max output tokens | Cap includes reasoning tokens | API |",
            "| --- | --- | ---: | --- | ---: | --- | --- |",
            *settings_rows,
            "",
            "Settings are taken from the first matching attempt of each configured model. Local and cloud attempts are not identical in sampling/reasoning configuration; this must be considered when comparing results, times, and token rates.",
        ])

    def profile_state(attempt):
        recorded = attempt.get("profile_hash")
        if recorded is None:
            return "unknown"
        for _path, profile, current_hash in profiles:
            if profile_matches(attempt, profile):
                return "current" if recorded == current_hash else "changed"
        return "unknown"

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
        "| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees | Profile |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ])
    for key, group in sorted(groups.items()):
        label, provider, model, task_hash, recorded_profile, scored, mock = key
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
        fee_incomplete = any(attempt.get("api_fee_incomplete") for attempt in group)
        run_type = "mock" if mock else ("scored" if scored else "pilot")
        acceptance = f"{len(accepted)}/{len(group)} ({len(accepted) / len(group):.0%})"
        median = duration(statistics.median(times) if times else None)
        identity = f"{provider} / {model}"
        profile_column = f"`{str(recorded_profile)[:12]}` ({profile_state(group[0])})"
        lines.append(
            f"| {cell(label)} | {cell(identity)} | {run_type} | `{task_hash[:12]}` | {len(group)} | {len(accepted)} | {acceptance} | {median} | {throughput(median_rate)} | {test_total(group, 'contract')} | {test_total(group, 'generated')} | {fee(total_fee, fee_incomplete)} | {profile_column} |"
        )

    lines.extend([
        "",
        "## Attempt Details",
        "",
        "| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens | Within budget | Fmt norm. |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ])
    for attempt in sorted(attempts, key=lambda item: item.get("created_at", "")):
        tokens = token_cell(attempt.get("native_usage_totals"))
        outcome = "accepted" if attempt.get("accepted") else attempt.get("category", "failed")
        stop = attempt.get("exit_status", attempt.get("category", "unknown"))
        normalized = attempt.get("normalized_action_response_count")
        lines.append(
            f"| {cell(attempt.get('label', 'unknown'))} | `{cell(attempt.get('attempt_id', 'unknown'))}` | {cell(outcome)} | {cell(stop)} | {duration(attempt.get('agent_seconds'))} | {duration(attempt.get('through_verification_seconds'))} | {throughput(attempt.get('completed_request_output_tokens_per_second'))} | {test_count(attempt, 'contract')} | {test_count(attempt, 'generated')} | {fee(attempt.get('api_fee_usd'), bool(attempt.get('api_fee_incomplete')))} | {tokens} | {yes_no(attempt.get('accepted_within_budget'))} | {'n/a' if normalized is None else normalized} |"
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
        "Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. For providers whose output cap includes reasoning tokens, output tokens/s counts reasoning tokens; reasoning tokens are listed separately in the token column when reported. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; \u2265 (incomplete) marks a lower bound where some requests lacked usage, and unknown means no fee could be computed. Fmt norm. counts responses whose extra action blocks were discarded. Local API fees exclude hardware and energy costs.",
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
    args.output.write_text(render_report(args.directory, frozen, profiles, args.title, freeze_name=args.freeze.name), encoding="utf-8")
    print(f"Comparison report written: {args.output}")


if __name__ == "__main__":
    main()
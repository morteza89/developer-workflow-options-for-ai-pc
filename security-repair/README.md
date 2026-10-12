# Security Repair

Option 3 is a focused source backport for PyJWT CVE-2022-29217 / GHSA-ffqj-6fqr-9h24. The task uses the vulnerable PyJWT 2.3.0 source at commit `24b29adfebcb4f057a3cef5aaf35653bc0c1c8cc`; its isolated reference overlays the repair from `9c528670c455b8d948aff95ed50e22940d1ad3fc`. The measured task can edit only `jwt/algorithms.py`, `jwt/utils.py`, and `tests/test_generated.py`.

The verifier rejects PEM and OpenSSH asymmetric key material used as an HMAC secret, checks ordinary HMAC plus RSA/ECDSA/EdDSA compatibility, and enforces the upstream EdDSA invalid-key exception contract. The task mount contains no Git history. Protected tests and the fixed reference remain outside it.

## Status

Offline qualification passed on Docker image `pyjwt-security:0.1`: the vulnerable source failed the injected regression tests; the upstream reference passed the contract, generated tests, and baseline-negative control; four deliberately defective repairs were rejected. The loopback demonstration and offline harness smoke are implemented. No local/cloud model was run, and the 240-second cutoff has not been measured. This result does not imply that Option 2 has been accepted.

## Setup and Checks

Prerequisites: Docker Desktop with Linux containers, Python 3.11, and the locked runner environment at `dependency-migration/.venv-runner`.

From the repository root in PowerShell:

```powershell
docker build --tag pyjwt-security:0.1 .\security-repair
.\dependency-migration\.venv-runner\Scripts\python.exe .\security-repair\qualify.py check --image pyjwt-security:0.1
.\dependency-migration\.venv-runner\Scripts\python.exe .\security-repair\bench.py freeze
.\dependency-migration\.venv-runner\Scripts\python.exe .\security-repair\bench.py smoke
```

Qualification runs the protected Docker checks on the vulnerable baseline, the pinned reference, and mutation controls. A freeze records current task, verifier, runner, and image hashes; it is not model qualification. Rebuild and requalify after changing the source snapshot, tests, lock, policy, runner, or image. Runtime reports and qualification logs are ignored under `security-repair/artifacts/`; the named default freeze is retained in version control.

To view the local demonstration after building the image, run `python .\security-repair\demo_server.py` from the repository root and open `http://127.0.0.1:8765/`. Each JSON request generates a fresh Ed25519 key and probes the vulnerable and patched source in read-only, network-disabled containers using the pinned task image. The server binds only to loopback.

Before a scored model run, qualify a model/profile, retain the profile outside source control if it contains local paths or private configuration, create a new freeze after any change, and run an accepted offline smoke for that exact freeze. No scored profile or model result is currently published. Never mount the reference, grader, qualification evidence, or proposal archive into the agent container.

## Files

- `starter/` contains the sanitized vulnerable snapshot, visible test, reproducer, task, and maintainer migration notes.
- `reference/` contains the pinned source repair and regression tests.
- `grader/` contains protected security and compatibility tests, mounted read-only during verification.
- `qualify.py` checks baseline/reference behavior and rejects four wrong-repair controls.
- `demo_server.py` serves a generated-key, loopback-only JSON comparison.
- `workflow.json`, `policy.json`, and `requirements-task.lock` pin task scope, timing, and image dependencies.

Source provenance and licensing are recorded in [SOURCE_NOTICES.md](SOURCE_NOTICES.md).
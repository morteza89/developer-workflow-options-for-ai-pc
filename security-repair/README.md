# Security Repair

Option 3 is a focused source backport for PyJWT CVE-2022-29217 / GHSA-ffqj-6fqr-9h24. The task uses the vulnerable PyJWT 2.3.0 source at commit `24b29adfebcb4f057a3cef5aaf35653bc0c1c8cc`; its isolated reference overlays the repair from `9c528670c455b8d948aff95ed50e22940d1ad3fc`. The measured task can edit only `jwt/algorithms.py`, `jwt/utils.py`, and `tests/test_generated.py`.

The verifier rejects PEM and OpenSSH asymmetric key material used as an HMAC secret, checks ordinary HMAC plus RSA/ECDSA/EdDSA compatibility, and enforces the upstream EdDSA invalid-key exception contract. The task mount contains no Git history. Protected tests and the fixed reference remain outside it.

## Status

Offline qualification passed on Docker image `pyjwt-security:0.1`: the vulnerable source failed the injected regression tests; the upstream reference passed the contract, generated tests, and baseline-negative control; four deliberately defective repairs were rejected. Under v5 at 240 seconds, 27B timed out after 7/8 protected checks with no generated assertions; 8B submitted after 52 seconds with 4/8 checks and no generated assertions. OpenAI passed 8/8 protected and 31/31 generated tests in 119 seconds. Under v7 at 600 seconds, 27B used 579 seconds, passed 6/8 protected checks and 7/7 generated tests, but missed RSA PEM/certificate and legacy PKCS#1 checks. The visible test now exercises those formats; v8 is the new 600-second comparison freeze. Results are unscored pilots, not qualification or acceptance claims.

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

## Model Demo Controller

After the image is built, the workflow is qualified, and the default freeze passes its offline smoke, double-click [Run-Demo.cmd](Run-Demo.cmd) to open the Windows GUI. It reuses the three configured profiles from `dependency-migration/profiles`: local Qwen3.8 27B, local Qwen3 8B, and GPT-6.1 Sol through the OpenAI API.

Choose a model in the GUI. For a local model, click **Start selected local model**, wait for `AVAILABLE`, then click **Test connection**. For OpenAI, select **GPT-6.1 Sol (OpenAI API)**, click **Set OpenAI API key**, paste into the masked popup, and choose **Use for this session**. The key stays in the GUI process environment for its child runner; it is not logged or saved. The OpenAI warmup and pilot require confirmation and are billable. Click **Run unscored pilot** to run this PyJWT task with its 600-second work budget, shared equally across all three models. Use **Open latest attempt**, **Refresh report**, or **Generate comparison report** to inspect results. The comparison report includes matching-freeze results and flags attempts from older freezes as needing a rerun.

If the selected freeze or image is stale/missing, prepare it using the setup commands above before starting a model run. A changed package must be re-frozen and smoke-tested; GUI runs do not build images or silently replace freezes.

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
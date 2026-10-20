# Source Notices

The immutable production snapshot in `starter/requests/` is Requests v2.31.0 from the public PSF Requests repository:

- Repository: https://github.com/psf/requests
- Exact commit: `147c8511ddbfa5e8f71bbf5c18ede0c4ceb3bba4`
- Tag: `v2.31.0` (annotated tag resolves to that commit)
- Source: https://github.com/psf/requests/tree/147c8511ddbfa5e8f71bbf5c18ede0c4ceb3bba4/requests
- License: Apache License 2.0, reproduced unchanged in [starter/LICENSE](starter/LICENSE).

Acquisition used `git clone --depth 1 --branch v2.31.0 https://github.com/psf/requests.git` into a temporary directory and verified `git rev-parse HEAD` against the exact commit above. Only the 18 production package files and upstream LICENSE were copied. All copied files were compared byte-for-byte by SHA-256 with that pinned checkout. No Git metadata, upstream tests, build configuration, or unrelated repository content is shipped in the task. The archive download was unsuccessful; Git acquisition succeeded.

[source-manifest.json](source-manifest.json) records SHA-256 hashes for each production file and LICENSE. Qualification rejects missing, additional, or changed production files. Production is not modified to create the task. Fault definitions in [workflow.json](workflow.json) are evaluator-only transformations of fresh copies; they do not alter the shipped snapshot. No duplicate production snapshot is stored under `reference/`.

The task instructions, visible examples, protected witnesses, human reference tests, qualification code, and task-specific metadata were authored for this package. The reference and witnesses use separate inputs and literal expected results; they are not copies of upstream tests. Dependency artifacts are separately pinned by hashes in [requirements-task.lock](requirements-task.lock); their original licenses remain with the distributions. No Requests distribution is installed into the task image: imports resolve to the pinned source in `/task/requests`.
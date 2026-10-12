# Source Notices

The task source snapshot is PyJWT, copyright 2015-2022 José Padilla, distributed under the MIT License. The license text is preserved at `starter/LICENSE.PyJWT` and `reference/LICENSE.PyJWT`.

The vulnerable source is derived from `jpadilla/pyjwt` commit `24b29adfebcb4f057a3cef5aaf35653bc0c1c8cc` (PyJWT 2.3.0). The isolated reference changes only `jwt/algorithms.py` and `jwt/utils.py` from the security repair at commit `9c528670c455b8d948aff95ed50e22940d1ad3fc`; version metadata remains at the starting revision because this task is a source backport, not a release.

Security issue: CVE-2022-29217, GHSA-ffqj-6fqr-9h24. The included source snapshot contains no Git metadata or future repository history. The benchmark reference and grader are outside the agent task mount.

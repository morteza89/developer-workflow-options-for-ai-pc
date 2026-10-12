"""Run the Security Repair task with the shared isolated workflow engine."""

import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent / "dependency-migration"
sys.path.insert(0, str(ENGINE_ROOT))

import bench as engine


if __name__ == "__main__":
    try:
        sys.exit(engine.main(package_root=Path(__file__).resolve().parent))
    except (ValueError, RuntimeError, OSError) as error:
        print(f"Blocked: {error}", file=sys.stderr)
        sys.exit(2)

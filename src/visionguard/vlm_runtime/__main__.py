"""Allow the managed runtime to start with ``python -m visionguard.vlm_runtime``."""

from visionguard.vlm_runtime.main import run

if __name__ == "__main__":
    raise SystemExit(run())

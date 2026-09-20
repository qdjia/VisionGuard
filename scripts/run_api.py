"""Launch the single-process VisionGuard inference API."""

import argparse

import uvicorn

from visionguard.api import create_app, load_api_config
from visionguard.core.logging import configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/api.yaml")
    parser.add_argument("--host", help="Override the configured bind host")
    parser.add_argument("--port", type=int, help="Override the configured bind port")
    parser.add_argument("--log-level", default="info")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging()
    config = load_api_config(args.config)
    uvicorn.run(
        create_app(config=config),
        host=args.host or config.api.host,
        port=args.port or config.api.port,
        log_level=args.log_level,
        workers=1,
        access_log=False,
    )


if __name__ == "__main__":
    main()

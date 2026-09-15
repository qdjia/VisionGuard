import argparse
import json
from pathlib import Path

from visionguard.moderation.policy import load_policy
from visionguard.vlm import create_provider, load_vlm_config
from visionguard.vlm.evaluator import evaluate_vlm


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/vlm.yaml"))
    parser.add_argument("--policy", type=Path, default=Path("configs/moderation_policy.yaml"))
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    config = load_vlm_config(args.config)
    if args.mock:
        config = config.model_copy(update={"provider": "mock", "experiment_name": "mock_vlm_v1"})
    print(
        json.dumps(
            evaluate_vlm(create_provider(config), load_policy(args.policy), args.manifest), indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

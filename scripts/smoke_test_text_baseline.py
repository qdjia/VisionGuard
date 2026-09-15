"""Small synthetic train/save/load/predict smoke test, not an accuracy experiment."""

from pathlib import Path
from tempfile import TemporaryDirectory

from visionguard.baseline import TextBaselineTrainer, TextModerationBaseline, load_baseline_config
from visionguard.core.logging import configure_logging


def main() -> int:
    configure_logging()
    with TemporaryDirectory(dir="artifacts", prefix="text_smoke_") as temporary:
        config = load_baseline_config("configs/baseline_text.yaml").model_copy(
            update={"artifacts_dir": Path(temporary)}
        )
        original = TextBaselineTrainer(config).train()
        loaded = TextModerationBaseline.load(config.artifacts_dir / config.experiment_name)
        texts = ["正常出版教材", "危险暴力伤害宣传"]
        before, after = original.predict_batch(texts), loaded.predict_batch(texts)
        assert [p.probability for p in before.predictions] == [
            p.probability for p in after.predictions
        ]
        print(after.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

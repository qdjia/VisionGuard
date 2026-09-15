from abc import ABC, abstractmethod

from visionguard.moderation.policy import ModerationPolicy
from visionguard.moderation.schemas import ModerationResult
from visionguard.utils.image import ImageInput
from visionguard.vlm.schemas import VLMContext


class VLMProvider(ABC):
    @abstractmethod
    def analyze(
        self, image: ImageInput, context: VLMContext, policy: ModerationPolicy
    ) -> ModerationResult: ...

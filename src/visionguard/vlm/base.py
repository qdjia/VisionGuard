from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from visionguard.moderation.policy import ModerationPolicy
from visionguard.moderation.schemas import ModerationResult
from visionguard.vlm.schemas import VLMContext

if TYPE_CHECKING:
    from visionguard.utils.image import ImageInput
else:
    ImageInput = Any


class VLMProvider(ABC):
    @abstractmethod
    def analyze(
        self, image: ImageInput, context: VLMContext, policy: ModerationPolicy
    ) -> ModerationResult: ...

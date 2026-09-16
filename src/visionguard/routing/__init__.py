"""Rule-based routing contracts and policy.

Evaluation and analysis helpers intentionally remain in their own modules.  Keeping
the public routing package limited to domain contracts avoids coupling the pipeline
bootstrap to experiment I/O code.
"""

from visionguard.routing.config import RoutingConfig, load_routing_config
from visionguard.routing.policy import RoutingPolicy
from visionguard.routing.schemas import (
    DecisionSource,
    Route,
    RoutingDecision,
    RoutingReasonCode,
    RoutingSignals,
)

__all__ = [
    "DecisionSource",
    "Route",
    "RoutingConfig",
    "RoutingDecision",
    "RoutingPolicy",
    "RoutingReasonCode",
    "RoutingSignals",
    "load_routing_config",
]

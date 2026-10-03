"""Parser registry — maps log family names to parser instances."""

from __future__ import annotations

from .base import BaseLogParser
from .fault_recovery_parser import FaultRecoveryParser
from .guidance_parser import GuidanceParser
from .operator_parser import OperatorParser
from .planning_parser import PlanningParser
from .state_parser import StateParser

# The registry maps log_family name → parser instance
# Add new parsers here when the official dataset arrives
PARSER_REGISTRY: dict[str, BaseLogParser] = {
    "operator": OperatorParser(),
    "planning": PlanningParser(),
    "guidance": GuidanceParser(),
    "state": StateParser(),
    "fault_recovery": FaultRecoveryParser(),
}


def get_parser(log_family: str) -> BaseLogParser | None:
    """Return the parser for the given family name, or None if unsupported."""
    return PARSER_REGISTRY.get(log_family)

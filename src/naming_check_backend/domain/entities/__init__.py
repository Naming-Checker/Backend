"""Domain entities."""

from naming_check_backend.domain.entities.check_request import (
    CheckRequest,
    FlowType,
    LogoComparisonPayload,
    ProcessingStatus,
    RegistrationPayload,
    TextInfringementPayload,
)
from naming_check_backend.domain.entities.conflict_result_set import (
    ConflictResultSet,
    MatchCandidate,
)
from naming_check_backend.domain.entities.stage2_job import DeliveryChannel, Stage2Job

__all__ = [
    "CheckRequest",
    "ConflictResultSet",
    "DeliveryChannel",
    "FlowType",
    "LogoComparisonPayload",
    "MatchCandidate",
    "ProcessingStatus",
    "RegistrationPayload",
    "Stage2Job",
    "TextInfringementPayload",
]

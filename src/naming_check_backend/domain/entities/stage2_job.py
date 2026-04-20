from dataclasses import dataclass
from enum import StrEnum

from naming_check_backend.domain.exceptions import DomainError


class DeliveryChannel(StrEnum):
    WEBHOOK = "webhook"


@dataclass(frozen=True, slots=True)
class Stage2Job:
    correlation_id: str
    dedup_key: str
    delivery: DeliveryChannel = DeliveryChannel.WEBHOOK
    partial_results_allowed: bool = True

    def __post_init__(self) -> None:
        if not self.correlation_id.strip():
            raise DomainError("correlation_id cannot be empty.")
        if not self.dedup_key.strip():
            raise DomainError("dedup_key cannot be empty.")

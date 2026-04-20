from dataclasses import dataclass
from enum import StrEnum

from naming_check_backend.domain.exceptions import DomainError
from naming_check_backend.domain.value_objects.logo import LogoAssetRef
from naming_check_backend.domain.value_objects.mktu import MktuClassSet
from naming_check_backend.domain.value_objects.naming import NamingText


class FlowType(StrEnum):
    REGISTRATION_CHECK = "registration_check"
    TEXT_INFRINGEMENT = "text_infringement"
    LOGO_COMPARISON = "logo_comparison"


class ProcessingStatus(StrEnum):
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RegistrationPayload:
    naming: NamingText


@dataclass(frozen=True, slots=True)
class TextInfringementPayload:
    protected_naming: NamingText
    suspicious_naming: NamingText


@dataclass(frozen=True, slots=True)
class LogoComparisonPayload:
    reference_logo: LogoAssetRef
    suspicious_logo: LogoAssetRef


@dataclass(frozen=True, slots=True)
class CheckRequest:
    request_id: str
    flow: FlowType
    status: ProcessingStatus
    mktu_codes: MktuClassSet
    payload: RegistrationPayload | TextInfringementPayload | LogoComparisonPayload

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise DomainError("request_id cannot be empty.")
        if self.flow is FlowType.REGISTRATION_CHECK and not isinstance(
            self.payload, RegistrationPayload
        ):
            raise DomainError("Registration flow requires RegistrationPayload.")
        if self.flow is FlowType.TEXT_INFRINGEMENT and not isinstance(
            self.payload, TextInfringementPayload
        ):
            raise DomainError("Text infringement flow requires TextInfringementPayload.")
        if self.flow is FlowType.LOGO_COMPARISON and not isinstance(
            self.payload, LogoComparisonPayload
        ):
            raise DomainError("Logo comparison flow requires LogoComparisonPayload.")

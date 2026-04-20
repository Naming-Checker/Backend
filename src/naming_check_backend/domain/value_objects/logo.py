from dataclasses import dataclass

from naming_check_backend.domain.exceptions import DomainError


@dataclass(frozen=True, slots=True)
class LogoAssetRef:
    asset_ref: str
    media_type: str | None = None
    filename: str | None = None

    def __post_init__(self) -> None:
        if not self.asset_ref.strip():
            raise DomainError("Logo asset reference cannot be empty.")

from dataclasses import dataclass

from naming_check_backend.domain.exceptions import DomainError


def normalize_naming(value: str) -> str:
    normalized = " ".join(value.split()).casefold()
    if not normalized:
        raise DomainError("Naming text cannot be empty after normalization.")
    return normalized


@dataclass(frozen=True, slots=True)
class NamingText:
    raw: str
    canonical: str

    @classmethod
    def from_raw(cls, raw: str) -> "NamingText":
        return cls(raw=raw, canonical=normalize_naming(raw))

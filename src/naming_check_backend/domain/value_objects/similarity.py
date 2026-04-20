from dataclasses import dataclass

from naming_check_backend.domain.exceptions import DomainError


def _validate_score(value: float, field_name: str) -> float:
    score = float(value)
    if not 0.0 <= score <= 100.0:
        raise DomainError(f"{field_name} must be within 0..100.")
    return score


@dataclass(frozen=True, slots=True)
class SimilarityBreakdown:
    semantic: float | None = None
    phonetic: float | None = None
    graphic: float | None = None
    legal: float | None = None
    visual: float | None = None

    def __post_init__(self) -> None:
        for field_name in ("semantic", "phonetic", "graphic", "legal", "visual"):
            value = getattr(self, field_name)
            if value is not None:
                _validate_score(value, field_name)


@dataclass(frozen=True, slots=True)
class SimilarityScore:
    total: float
    breakdown: SimilarityBreakdown | None = None

    def __post_init__(self) -> None:
        _validate_score(self.total, "total")

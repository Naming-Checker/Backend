from dataclasses import dataclass, field

from naming_check_backend.domain.exceptions import DomainError
from naming_check_backend.domain.value_objects.mktu import MktuClassSet
from naming_check_backend.domain.value_objects.similarity import SimilarityScore


@dataclass(frozen=True, slots=True)
class MatchCandidate:
    candidate_id: str
    candidate_name: str
    source: str
    mktu_codes: MktuClassSet
    similarity: SimilarityScore
    summary: str | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise DomainError("candidate_id cannot be empty.")
        if not self.candidate_name.strip():
            raise DomainError("candidate_name cannot be empty.")
        if not self.source.strip():
            raise DomainError("source cannot be empty.")


@dataclass(frozen=True, slots=True)
class ConflictResultSet:
    request_id: str
    candidates: tuple[MatchCandidate, ...] = field(default_factory=tuple)
    result_limit: int = 200
    partial: bool = False

    def __post_init__(self) -> None:
        if self.result_limit <= 0:
            raise DomainError("result_limit must be positive.")
        if len(self.candidates) > self.result_limit:
            raise DomainError("Candidate count cannot exceed result_limit.")

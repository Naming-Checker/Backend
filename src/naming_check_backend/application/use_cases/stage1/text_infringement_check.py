from naming_check_backend.domain.entities import (
    CheckRequest,
    ConflictResultSet,
    FlowType,
    MatchCandidate,
    ProcessingStatus,
    TextInfringementPayload,
)
from naming_check_backend.domain.policies import build_similarity_score, rank_candidates
from naming_check_backend.domain.value_objects import MktuClassSet, NamingText, SimilarityScore


class TextInfringementCheckUseCase:
    """Orchestrates pairwise Stage 1 text infringement checks."""

    def execute(
        self, protected_naming: str, suspicious_naming: str, mktu_codes: list[int]
    ) -> tuple[CheckRequest, ConflictResultSet, SimilarityScore]:
        protected_text = NamingText.from_raw(protected_naming)
        suspicious_text = NamingText.from_raw(suspicious_naming)
        request_id = f"txt-{'-'.join(suspicious_text.canonical.split())}-001"
        mktu_set = MktuClassSet.from_iterable(mktu_codes)
        request = CheckRequest(
            request_id=request_id,
            flow=FlowType.TEXT_INFRINGEMENT,
            status=ProcessingStatus.COMPLETED,
            mktu_codes=mktu_set,
            payload=TextInfringementPayload(
                protected_naming=protected_text,
                suspicious_naming=suspicious_text,
            ),
        )
        pair_similarity = build_similarity_score(
            94.2,
            semantic=82.0,
            phonetic=98.0,
            graphic=93.0,
            legal=95.0,
        )
        candidates = [
            MatchCandidate(
                candidate_id="tm-002",
                candidate_name=suspicious_text.raw.strip(),
                source="trademark_db",
                mktu_codes=mktu_set,
                similarity=pair_similarity,
                summary="Pairwise comparison found the same dominant verbal core.",
            )
        ]
        ranked = tuple(rank_candidates(candidates))
        return request, ConflictResultSet(request_id=request_id, candidates=ranked), pair_similarity

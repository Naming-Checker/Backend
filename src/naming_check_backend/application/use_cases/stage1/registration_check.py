from naming_check_backend.domain.entities import (
    CheckRequest,
    ConflictResultSet,
    FlowType,
    MatchCandidate,
    ProcessingStatus,
    RegistrationPayload,
)
from naming_check_backend.domain.policies import build_similarity_score, rank_candidates
from naming_check_backend.domain.value_objects import MktuClassSet, NamingText


class RegistrationCheckUseCase:
    """Orchestrates the internal Stage 1 registration check flow."""

    def execute(self, naming: str, mktu_codes: list[int]) -> tuple[CheckRequest, ConflictResultSet]:
        naming_text = NamingText.from_raw(naming)
        request_id = f"reg-{'-'.join(naming_text.canonical.split())}-001"
        mktu_set = MktuClassSet.from_iterable(mktu_codes)
        request = CheckRequest(
            request_id=request_id,
            flow=FlowType.REGISTRATION_CHECK,
            status=ProcessingStatus.COMPLETED,
            mktu_codes=mktu_set,
            payload=RegistrationPayload(naming=naming_text),
        )
        candidates = [
            MatchCandidate(
                candidate_id="tm-001",
                candidate_name=f"{naming_text.raw.strip()} PRIME",
                source="trademark_db",
                mktu_codes=mktu_set,
                similarity=build_similarity_score(
                    91.4,
                    semantic=84.0,
                    phonetic=96.0,
                    graphic=88.0,
                    legal=90.0,
                ),
                summary="Internal trademark candidate with a strong phonetic and legal overlap.",
            )
        ]
        ranked = tuple(rank_candidates(candidates))
        return request, ConflictResultSet(request_id=request_id, candidates=ranked)

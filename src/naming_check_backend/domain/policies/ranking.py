from naming_check_backend.domain.entities.conflict_result_set import MatchCandidate


def rank_candidates(
    candidates: list[MatchCandidate], result_limit: int = 200
) -> list[MatchCandidate]:
    ranked = sorted(
        candidates,
        key=lambda candidate: (-candidate.similarity.total, candidate.candidate_id),
    )
    return ranked[:result_limit]

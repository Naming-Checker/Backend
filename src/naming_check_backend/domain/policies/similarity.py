from naming_check_backend.domain.value_objects.similarity import (
    SimilarityBreakdown,
    SimilarityScore,
)


def build_similarity_score(
    total: float,
    *,
    semantic: float | None = None,
    phonetic: float | None = None,
    graphic: float | None = None,
    legal: float | None = None,
    visual: float | None = None,
) -> SimilarityScore:
    breakdown = SimilarityBreakdown(
        semantic=semantic,
        phonetic=phonetic,
        graphic=graphic,
        legal=legal,
        visual=visual,
    )
    return SimilarityScore(total=total, breakdown=breakdown)

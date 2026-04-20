from naming_check_backend.domain.entities import CheckRequest, ConflictResultSet, MatchCandidate
from naming_check_backend.domain.value_objects import (
    LogoAssetRef,
)
from naming_check_backend.domain.value_objects import (
    SimilarityBreakdown as DomainBreakdown,
)
from naming_check_backend.presentation.schemas.contracts import (
    FlowType,
    LogoAssetReference,
    ProcessingStatus,
    SimilarityBreakdown,
    Stage1Meta,
    Stage2StatusInfo,
)
from naming_check_backend.presentation.schemas.contracts import (
    MatchCandidate as MatchCandidateSchema,
)


def to_logo_asset_ref(dto: LogoAssetReference) -> LogoAssetRef:
    return LogoAssetRef(asset_ref=dto.asset_ref, media_type=dto.media_type, filename=dto.filename)


def _to_similarity_breakdown(breakdown: DomainBreakdown | None) -> SimilarityBreakdown | None:
    if breakdown is None:
        return None
    return SimilarityBreakdown(
        semantic=breakdown.semantic,
        phonetic=breakdown.phonetic,
        graphic=breakdown.graphic,
        legal=breakdown.legal,
        visual=breakdown.visual,
    )


def to_match_candidate(candidate: MatchCandidate) -> MatchCandidateSchema:
    return MatchCandidateSchema(
        candidate_id=candidate.candidate_id,
        candidate_name=candidate.candidate_name,
        source=candidate.source,
        mktu_codes=candidate.mktu_codes.as_list(),
        similarity=candidate.similarity.total,
        summary=candidate.summary,
        similarity_breakdown=_to_similarity_breakdown(candidate.similarity.breakdown),
    )


def to_stage2_status(check_request: CheckRequest) -> Stage2StatusInfo:
    return Stage2StatusInfo(
        status=ProcessingStatus.ACCEPTED,
        correlation_id=check_request.request_id,
    )


def to_stage1_meta(result_set: ConflictResultSet) -> Stage1Meta:
    return Stage1Meta(
        internal_result_count=len(result_set.candidates),
        result_limit=result_set.result_limit,
        stage2_enabled=True,
    )


def to_flow_type(check_request: CheckRequest) -> FlowType:
    return FlowType(check_request.flow.value)


def to_processing_status(check_request: CheckRequest) -> ProcessingStatus:
    return ProcessingStatus(check_request.status.value)

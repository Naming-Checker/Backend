import pytest

from naming_check_backend.domain.entities import (
    CheckRequest,
    ConflictResultSet,
    FlowType,
    LogoComparisonPayload,
    MatchCandidate,
    ProcessingStatus,
    RegistrationPayload,
    TextInfringementPayload,
)
from naming_check_backend.domain.exceptions import DomainError
from naming_check_backend.domain.policies import build_similarity_score, rank_candidates
from naming_check_backend.domain.value_objects import LogoAssetRef, MktuClassSet, NamingText


def test_naming_text_builds_canonical_value() -> None:
    naming = NamingText.from_raw("  PROBI   MAX ")

    assert naming.canonical == "probi max"


def test_mktu_set_is_sorted_and_deduplicated() -> None:
    mktu_set = MktuClassSet.from_iterable([25, 5, 25])

    assert mktu_set.values == (5, 25)


def test_check_request_validates_flow_payload_pair() -> None:
    with pytest.raises(DomainError):
        CheckRequest(
            request_id="req-1",
            flow=FlowType.REGISTRATION_CHECK,
            status=ProcessingStatus.COMPLETED,
            mktu_codes=MktuClassSet.from_iterable([5]),
            payload=TextInfringementPayload(
                protected_naming=NamingText.from_raw("A"),
                suspicious_naming=NamingText.from_raw("B"),
            ),
        )


def test_conflict_result_set_respects_limit() -> None:
    candidate = MatchCandidate(
        candidate_id="id-1",
        candidate_name="Name",
        source="trademark_db",
        mktu_codes=MktuClassSet.from_iterable([5]),
        similarity=build_similarity_score(80),
    )

    with pytest.raises(DomainError):
        ConflictResultSet(request_id="r1", candidates=(candidate,), result_limit=0)


def test_rank_candidates_sorts_by_similarity_then_id() -> None:
    mktu = MktuClassSet.from_iterable([5])
    candidates = [
        MatchCandidate(
            candidate_id="b",
            candidate_name="B",
            source="source",
            mktu_codes=mktu,
            similarity=build_similarity_score(90),
        ),
        MatchCandidate(
            candidate_id="a",
            candidate_name="A",
            source="source",
            mktu_codes=mktu,
            similarity=build_similarity_score(90),
        ),
        MatchCandidate(
            candidate_id="c",
            candidate_name="C",
            source="source",
            mktu_codes=mktu,
            similarity=build_similarity_score(75),
        ),
    ]

    ranked = rank_candidates(candidates)

    assert [candidate.candidate_id for candidate in ranked] == ["a", "b", "c"]


def test_logo_payload_accepts_non_empty_asset_ref() -> None:
    payload = LogoComparisonPayload(
        reference_logo=LogoAssetRef(asset_ref="logo://a"),
        suspicious_logo=LogoAssetRef(asset_ref="logo://b"),
    )
    request = CheckRequest(
        request_id="logo-1",
        flow=FlowType.LOGO_COMPARISON,
        status=ProcessingStatus.COMPLETED,
        mktu_codes=MktuClassSet.from_iterable([35]),
        payload=payload,
    )

    assert request.request_id == "logo-1"


def test_registration_payload_value_object() -> None:
    payload = RegistrationPayload(naming=NamingText.from_raw("Probimax"))

    assert payload.naming.canonical == "probimax"

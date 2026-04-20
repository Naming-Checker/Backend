from naming_check_backend.application.use_cases.stage1.logo_comparison import LogoComparisonUseCase
from naming_check_backend.application.use_cases.stage1.registration_check import (
    RegistrationCheckUseCase,
)
from naming_check_backend.application.use_cases.stage1.text_infringement_check import (
    TextInfringementCheckUseCase,
)
from naming_check_backend.domain.entities import FlowType
from naming_check_backend.domain.value_objects import LogoAssetRef


def test_registration_use_case_returns_domain_objects() -> None:
    use_case = RegistrationCheckUseCase()

    request, result_set = use_case.execute("PROBIMAX", [5, 25])

    assert request.flow is FlowType.REGISTRATION_CHECK
    assert result_set.request_id == request.request_id
    assert len(result_set.candidates) == 1


def test_text_infringement_use_case_returns_pair_similarity() -> None:
    use_case = TextInfringementCheckUseCase()

    request, result_set, pair_similarity = use_case.execute("PROBIMAX", "PROBI MAX", [5])

    assert request.flow is FlowType.TEXT_INFRINGEMENT
    assert result_set.request_id == request.request_id
    assert pair_similarity.total == 94.2


def test_logo_comparison_use_case_uses_logo_refs() -> None:
    use_case = LogoComparisonUseCase()

    request, result_set, summary = use_case.execute(
        LogoAssetRef(asset_ref="logo://protected/probimax-main"),
        LogoAssetRef(asset_ref="logo://suspicious/probi-market"),
        [35],
    )

    assert request.flow is FlowType.LOGO_COMPARISON
    assert result_set.request_id == request.request_id
    assert summary.startswith("Placeholder Stage 1 response")

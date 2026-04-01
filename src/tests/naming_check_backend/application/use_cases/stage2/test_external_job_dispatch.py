from naming_check_backend.application.use_cases.stage2.external_job_dispatch import (
    ExternalJobDispatchUseCase,
)


def test_external_job_dispatch_builds_deduplicated_webhook_job() -> None:
    use_case = ExternalJobDispatchUseCase()

    job = use_case.build_job("Probimax", [35, 25, 35])

    assert job == {
        "naming": "Probimax",
        "mktu_codes": [25, 35],
        "dedup_key": "probimax|25,35",
        "delivery": "webhook",
    }

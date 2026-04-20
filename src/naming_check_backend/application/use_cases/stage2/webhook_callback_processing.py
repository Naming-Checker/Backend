from naming_check_backend.domain.entities import Stage2Job


class WebhookCallbackProcessingUseCase:
    """Process Stage 2 webhook callbacks in an idempotent way."""

    def execute(self, correlation_id: str, partial: bool) -> Stage2Job:
        return Stage2Job(
            correlation_id=correlation_id,
            dedup_key=correlation_id,
            partial_results_allowed=partial,
        )

class AsyncFlowThresholds:
    """Operational thresholds for the Stage 2 async flow."""

    delay_minutes: int = 5
    fail_rate_percent: int = 2
    dlq_threshold: int = 5

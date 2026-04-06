from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FlowType(StrEnum):
    REGISTRATION_CHECK = "registration_check"
    TEXT_INFRINGEMENT = "text_infringement"
    LOGO_COMPARISON = "logo_comparison"


class ProcessingStatus(StrEnum):
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class DeliveryChannel(StrEnum):
    WEBHOOK = "webhook"


class ErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    VALIDATION_ERROR = "validation_error"
    CONFLICT = "conflict"
    INTERNAL_ERROR = "internal_error"


class SimilarityBreakdown(BaseModel):
    semantic: float | None = Field(default=None, ge=0, le=100)
    phonetic: float | None = Field(default=None, ge=0, le=100)
    graphic: float | None = Field(default=None, ge=0, le=100)
    legal: float | None = Field(default=None, ge=0, le=100)
    visual: float | None = Field(default=None, ge=0, le=100)


class MatchCandidate(BaseModel):
    candidate_id: str = Field(description="Stable identifier of the matched candidate.")
    candidate_name: str = Field(description="Human-readable name of the matched candidate.")
    source: str = Field(description="Source system that produced the candidate.")
    mktu_codes: list[int] = Field(default_factory=list)
    similarity: float = Field(ge=0, le=100)
    summary: str | None = Field(default=None, description="Short explanation of why it matched.")
    similarity_breakdown: SimilarityBreakdown | None = None


class Stage1Meta(BaseModel):
    internal_result_count: int = Field(ge=0)
    result_limit: int = Field(default=200, ge=1, le=200)
    stage2_enabled: bool = True


class Stage2StatusInfo(BaseModel):
    status: ProcessingStatus
    delivery: DeliveryChannel = DeliveryChannel.WEBHOOK
    correlation_id: str
    partial_results_allowed: bool = True
    webhook_path: str = "/api/v1/webhooks/stage2-results"


class ErrorContext(BaseModel):
    field: str | None = None
    details: dict[str, str] = Field(default_factory=dict)


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    context: ErrorContext | None = None


class ErrorResponse(BaseModel):
    status: str = "error"
    error: ErrorDetail

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "error",
                "error": {
                    "code": "invalid_input",
                    "message": "At least one Nice class is required.",
                    "context": {"field": "mktu_codes", "details": {"reason": "empty_list"}},
                },
            }
        }
    )


class RegistrationCheckRequest(BaseModel):
    naming: str = Field(min_length=1, description="Naming to validate for registration.")
    mktu_codes: list[int] = Field(
        min_length=1,
        description="Nice classes used for candidate filtering and Stage 2 deduplication.",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"naming": "PROBIMAX", "mktu_codes": [5, 25]}}
    )


class RegistrationCheckResponse(BaseModel):
    request_id: str
    flow: FlowType = FlowType.REGISTRATION_CHECK
    status: ProcessingStatus = ProcessingStatus.COMPLETED
    naming: str
    mktu_codes: list[int]
    internal_results: list[MatchCandidate] = Field(default_factory=list)
    stage2: Stage2StatusInfo
    meta: Stage1Meta

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "reg-probimax-001",
                "flow": "registration_check",
                "status": "completed",
                "naming": "PROBIMAX",
                "mktu_codes": [5, 25],
                "internal_results": [
                    {
                        "candidate_id": "tm-001",
                        "candidate_name": "PROBI MAX",
                        "source": "trademark_db",
                        "mktu_codes": [5, 25],
                        "similarity": 91.4,
                        "summary": "High phonetic overlap in the same Nice classes.",
                        "similarity_breakdown": {
                            "semantic": 84.0,
                            "phonetic": 96.0,
                            "graphic": 88.0,
                            "legal": 90.0,
                        },
                    }
                ],
                "stage2": {
                    "status": "accepted",
                    "delivery": "webhook",
                    "correlation_id": "reg-probimax-001",
                    "partial_results_allowed": True,
                    "webhook_path": "/api/v1/webhooks/stage2-results",
                },
                "meta": {
                    "internal_result_count": 1,
                    "result_limit": 200,
                    "stage2_enabled": True,
                },
            }
        }
    )


class TextInfringementRequest(BaseModel):
    protected_naming: str = Field(min_length=1)
    suspicious_naming: str = Field(min_length=1)
    mktu_codes: list[int] = Field(
        default_factory=list,
        description="Optional Nice classes that narrow matching and dedup Stage 2 jobs.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "protected_naming": "PROBIMAX",
                "suspicious_naming": "PROBI MAX",
                "mktu_codes": [5],
            }
        }
    )


class TextInfringementResponse(BaseModel):
    request_id: str
    flow: FlowType = FlowType.TEXT_INFRINGEMENT
    status: ProcessingStatus = ProcessingStatus.COMPLETED
    protected_naming: str
    suspicious_naming: str
    mktu_codes: list[int]
    pair_similarity: float = Field(ge=0, le=100)
    internal_results: list[MatchCandidate] = Field(default_factory=list)
    stage2: Stage2StatusInfo
    meta: Stage1Meta

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "txt-probi-001",
                "flow": "text_infringement",
                "status": "completed",
                "protected_naming": "PROBIMAX",
                "suspicious_naming": "PROBI MAX",
                "mktu_codes": [5],
                "pair_similarity": 94.2,
                "internal_results": [
                    {
                        "candidate_id": "tm-002",
                        "candidate_name": "PROBI-MAX",
                        "source": "trademark_db",
                        "mktu_codes": [5],
                        "similarity": 94.2,
                        "summary": "Shared dominant verbal core.",
                        "similarity_breakdown": {
                            "semantic": 82.0,
                            "phonetic": 98.0,
                            "graphic": 93.0,
                            "legal": 95.0,
                        },
                    }
                ],
                "stage2": {
                    "status": "accepted",
                    "delivery": "webhook",
                    "correlation_id": "txt-probi-001",
                    "partial_results_allowed": True,
                    "webhook_path": "/api/v1/webhooks/stage2-results",
                },
                "meta": {
                    "internal_result_count": 1,
                    "result_limit": 200,
                    "stage2_enabled": True,
                },
            }
        }
    )


class LogoAssetReference(BaseModel):
    asset_ref: str = Field(
        min_length=1,
        description="Opaque placeholder reference to the logo payload or stored file.",
    )
    media_type: str | None = Field(
        default=None,
        description="Optional media type hint until the file transport is finalized.",
    )
    filename: str | None = None


class LogoComparisonRequest(BaseModel):
    reference_logo: LogoAssetReference
    suspicious_logo: LogoAssetReference
    mktu_codes: list[int] = Field(default_factory=list)
    notes: str | None = Field(
        default=None,
        description="Optional business context for the placeholder logo contract.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reference_logo": {
                    "asset_ref": "logo://protected/probimax-main",
                    "media_type": "image/png",
                    "filename": "probimax.png",
                },
                "suspicious_logo": {
                    "asset_ref": "logo://suspicious/probi-market",
                    "media_type": "image/png",
                    "filename": "probi-market.png",
                },
                "mktu_codes": [35],
                "notes": "Placeholder contract until final binary transport is approved.",
            }
        }
    )


class LogoComparisonResponse(BaseModel):
    request_id: str
    flow: FlowType = FlowType.LOGO_COMPARISON
    status: ProcessingStatus = ProcessingStatus.COMPLETED
    reference_logo: LogoAssetReference
    suspicious_logo: LogoAssetReference
    mktu_codes: list[int]
    internal_results: list[MatchCandidate] = Field(default_factory=list)
    comparison_summary: str
    stage2: Stage2StatusInfo
    meta: Stage1Meta

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "logo-probi-001",
                "flow": "logo_comparison",
                "status": "completed",
                "reference_logo": {
                    "asset_ref": "logo://protected/probimax-main",
                    "media_type": "image/png",
                    "filename": "probimax.png",
                },
                "suspicious_logo": {
                    "asset_ref": "logo://suspicious/probi-market",
                    "media_type": "image/png",
                    "filename": "probi-market.png",
                },
                "mktu_codes": [35],
                "internal_results": [
                    {
                        "candidate_id": "logo-001",
                        "candidate_name": "Probimax visual mark",
                        "source": "trademark_db",
                        "mktu_codes": [35],
                        "similarity": 88.6,
                        "summary": "Similar visual silhouette and retained text element.",
                        "similarity_breakdown": {"visual": 88.6, "legal": 85.0},
                    }
                ],
                "comparison_summary": "Placeholder response with internal logo matches.",
                "stage2": {
                    "status": "accepted",
                    "delivery": "webhook",
                    "correlation_id": "logo-probi-001",
                    "partial_results_allowed": True,
                    "webhook_path": "/api/v1/webhooks/stage2-results",
                },
                "meta": {
                    "internal_result_count": 1,
                    "result_limit": 200,
                    "stage2_enabled": True,
                },
            }
        }
    )


class Stage2WebhookRequest(BaseModel):
    correlation_id: str
    flow: FlowType
    status: ProcessingStatus = ProcessingStatus.PARTIAL
    naming: str | None = None
    subject_ref: str | None = None
    mktu_codes: list[int] = Field(default_factory=list)
    partial: bool = True
    matches: list[MatchCandidate] = Field(default_factory=list)
    source_batch: list[str] = Field(default_factory=list)
    error: ErrorDetail | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "correlation_id": "reg-probimax-001",
                "flow": "registration_check",
                "status": "partial",
                "naming": "PROBIMAX",
                "mktu_codes": [5, 25],
                "partial": True,
                "matches": [
                    {
                        "candidate_id": "ext-001",
                        "candidate_name": "Probimax Mobile",
                        "source": "google_play",
                        "mktu_codes": [9],
                        "similarity": 81.0,
                        "summary": "Found in external store search.",
                        "similarity_breakdown": {"semantic": 77.0, "phonetic": 86.0},
                    }
                ],
                "source_batch": ["google_play"],
            }
        }
    )


class Stage2WebhookResponse(BaseModel):
    status: ProcessingStatus = ProcessingStatus.ACCEPTED
    delivery: DeliveryChannel = DeliveryChannel.WEBHOOK
    processing_status: ProcessingStatus = ProcessingStatus.ACCEPTED
    correlation_id: str
    partial: bool
    use_case: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "accepted",
                "delivery": "webhook",
                "processing_status": "accepted",
                "correlation_id": "reg-probimax-001",
                "partial": True,
                "use_case": "WebhookCallbackProcessingUseCase",
            }
        }
    )

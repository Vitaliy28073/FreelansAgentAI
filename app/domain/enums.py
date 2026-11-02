from __future__ import annotations

from enum import StrEnum


class SourceCode(StrEnum):
    FL_RSS = "fl_rss"
    FREELANCEHUNT = "freelancehunt"


class ConnectorStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    PAUSED = "paused"
    AUTH_REQUIRED = "auth_required"
    FORBIDDEN = "forbidden"
    RATE_LIMITED = "rate_limited"
    CHALLENGE = "challenge"
    UNAVAILABLE = "unavailable"
    MANUAL_REVIEW = "manual_review_required"


class JobStatus(StrEnum):
    NEW = "new"
    ANALYZED = "analyzed"
    SHORTLISTED = "shortlisted"
    DRAFT_READY = "draft_ready"
    APPROVED = "approved"
    APPLIED_MANUALLY = "applied_manually"
    SENT_VIA_AUTHORIZED_API = "sent_via_authorized_api"
    REPLIED = "replied"
    INTERVIEW = "interview"
    WON = "won"
    LOST = "lost"
    EXPIRED = "expired"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    FILTERED_OUT = "filtered_out"


class AnalysisDecision(StrEnum):
    APPLY = "apply"
    CONSIDER = "consider"
    SKIP = "skip"
    MANUAL_REVIEW = "manual_review"


class DraftStyle(StrEnum):
    SHORT = "short"
    STANDARD = "standard"
    TECHNICAL = "technical"


class ErrorCode(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    CHALLENGE_DETECTED = "CHALLENGE_DETECTED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"

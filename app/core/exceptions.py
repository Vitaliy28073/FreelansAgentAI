from __future__ import annotations


class RadarError(Exception):
    code: str = "UNKNOWN_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class ConnectorError(RadarError):
    code = "UNKNOWN_ERROR"


class AuthRequiredError(ConnectorError):
    code = "AUTH_REQUIRED"


class ForbiddenError(ConnectorError):
    code = "FORBIDDEN"


class RateLimitedError(ConnectorError):
    code = "RATE_LIMITED"

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ChallengeDetectedError(ConnectorError):
    code = "CHALLENGE_DETECTED"


class SourceUnavailableError(ConnectorError):
    code = "SOURCE_UNAVAILABLE"


class SchemaChangedError(ConnectorError):
    code = "SCHEMA_CHANGED"


class LLMError(RadarError):
    code = "LLM_ERROR"


class LLMUnavailableError(LLMError):
    code = "AI_UNAVAILABLE"


class AccessDeniedError(RadarError):
    code = "ACCESS_DENIED"

from __future__ import annotations

from app.connectors.base import BaseConnector
from app.connectors.fl_rss import FlRssConnector
from app.connectors.freelancehunt_api import FreelancehuntConnector
from app.core.config import Settings
from app.domain.enums import SourceCode


def build_connectors(settings: Settings, *, freelancehunt_token: str = "") -> dict[SourceCode, BaseConnector]:
    connectors: dict[SourceCode, BaseConnector] = {}
    if settings.fl_rss_enabled:
        connectors[SourceCode.FL_RSS] = FlRssConnector(settings)
    if settings.freelancehunt_enabled and (freelancehunt_token or settings.freelancehunt_token):
        connectors[SourceCode.FREELANCEHUNT] = FreelancehuntConnector(
            settings, freelancehunt_token or settings.freelancehunt_token
        )
    return connectors

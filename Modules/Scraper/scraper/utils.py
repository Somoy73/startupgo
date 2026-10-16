"""Small pure helpers shared by adapters."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urljoin

from .models import StartupLead


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def absolute_url(value: object, base_url: str) -> str:
    return urljoin(base_url, clean(value))


def deduplicate(leads: Iterable[StartupLead]) -> list[StartupLead]:
    unique: dict[str, StartupLead] = {}
    for lead in leads:
        unique.setdefault(lead.key(), lead)
    return list(unique.values())

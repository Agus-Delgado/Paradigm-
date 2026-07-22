"""Readable, unique run identifiers for experiment runs."""

from __future__ import annotations

import re
from datetime import datetime, timezone


_SLUG_RE = re.compile(r"[^a-z0-9_-]+")


def slugify(name: str) -> str:
    """Normalize a human name into a filesystem-safe slug."""
    text = name.strip().lower().replace(" ", "_")
    text = _SLUG_RE.sub("_", text)
    text = re.sub(r"_+", "_", text).strip("_-")
    return text or "experiment"


def generate_run_id(
    name: str,
    *,
    when: datetime | None = None,
    suffix: str | None = None,
) -> str:
    """Build a unique, human-readable run id.

    Format: ``YYYYMMDD_HHMMSS_<slug>`` or ``YYYYMMDD_HHMMSS_<slug>_<suffix>``.

    ``when`` defaults to current UTC. Passing an explicit ``when`` (and optional
    ``suffix``) makes the id deterministic for the same inputs.
    """
    moment = when or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.astimezone(timezone.utc)

    stamp = moment.strftime("%Y%m%d_%H%M%S")
    slug = slugify(name)
    if suffix:
        safe_suffix = slugify(suffix)
        return f"{stamp}_{slug}_{safe_suffix}"
    return f"{stamp}_{slug}"

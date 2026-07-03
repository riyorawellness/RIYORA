"""Sanitizers for user-supplied query/search inputs.

MongoDB operator injection is prevented by never accepting raw dicts as query
values. This helper strips leading `$` from string search terms which prevents
regex-based DOS and NoSQL-operator-in-string tricks.
"""
from __future__ import annotations

import re

_DANGEROUS = re.compile(r"[\$\{\}]")


def clean_search(q: str | None, max_len: int = 100) -> str | None:
    if q is None:
        return None
    q = str(q).strip()[:max_len]
    q = _DANGEROUS.sub("", q)
    # Escape regex-special chars so we can't build a catastrophic regex.
    return re.escape(q) if q else None

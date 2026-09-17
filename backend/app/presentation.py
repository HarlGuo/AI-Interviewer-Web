from __future__ import annotations

import re

INTERNAL_LINE_REFERENCE = re.compile(
    r"(?:[（(\[]\s*)?\bL\d{2,4}(?:\s*[-–—~至]\s*L?\d{2,4})?\b(?:\s*[）)\]])?\s*[：:]?\s*",
    re.IGNORECASE,
)


def clean_user_facing_text(value: str) -> str:
    return re.sub(r"\s{2,}", " ", INTERNAL_LINE_REFERENCE.sub("", value)).strip()

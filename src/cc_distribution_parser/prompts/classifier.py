"""3-class document classifier prompt.

# TODO: tune SYSTEM_PROMPT + few-shots with real CC/Distribution PDFs.
The structural seam (version, compute_hash, SYSTEM/USER templates) is
locked; content is placeholder.
"""

from __future__ import annotations

import hashlib

version = "classifier@0.1.0"

SYSTEM_PROMPT = """You classify private-equity fund-administration notices into one of:
- capital_call: a notice requesting an investor to send capital to the fund
- distribution: a notice that the fund is paying capital out to the investor
- other_or_reject: anything else (statement, K-1, marketing, malformed)

Respond with reasoning first, then the label and a confidence in [0, 1].
"""

USER_TEMPLATE = """Document:
{document}

Return your classification as structured output."""

FEW_SHOT_TEMPLATE = """Example {idx}:
Document excerpt: {excerpt}
Label: {label}
Reasoning: {reasoning}
"""


def compute_hash(rendered: str) -> str:
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()

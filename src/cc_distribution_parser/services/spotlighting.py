"""Spotlighting — wrap untrusted document text in delimiters.

Per ~/.claude/ai-build-team/rules/prompt-injection.md (mandatory for this
project per overrides.md): the LLM is instructed to treat anything between
the delimiters as DATA, never INSTRUCTIONS. The test for this defense is
that the bad string only appears INSIDE the wrap (build-lead lesson
2026-05-01 "Test the security property, not the input string").
"""

from __future__ import annotations

OPEN_DELIM = "<<<UNTRUSTED_DOCUMENT_BEGIN>>>"
CLOSE_DELIM = "<<<UNTRUSTED_DOCUMENT_END>>>"


def wrap(untrusted: str) -> str:
    """Wrap untrusted text. Strips any pre-existing close-delim to prevent
    closing-delim smuggling."""
    sanitized = untrusted.replace(CLOSE_DELIM, "")
    return f"{OPEN_DELIM}\n{sanitized}\n{CLOSE_DELIM}"


def extract_wrapped_region(output: str) -> tuple[str, str]:
    """For tests: split output into (outside, inside) the wrap.

    Returns ("", output) if delimiters not present — caller asserts as appropriate.
    """
    open_idx = output.find(OPEN_DELIM)
    close_idx = output.rfind(CLOSE_DELIM)
    if open_idx == -1 or close_idx == -1 or close_idx <= open_idx:
        return ("", output)
    inside_start = open_idx + len(OPEN_DELIM)
    outside = output[:open_idx] + output[close_idx + len(CLOSE_DELIM) :]
    inside = output[inside_start:close_idx]
    return (outside, inside)

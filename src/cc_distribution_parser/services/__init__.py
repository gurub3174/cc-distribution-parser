"""Service functions.

Each module exports `def run(state: DocState) -> DocState`. Framework-free
(no LangGraph imports — that's `workflow/`s job). Side effects on external
systems (S3, Snowflake, Bedrock) are isolated to dedicated helpers in the
same module so they can be patched in unit tests.
"""

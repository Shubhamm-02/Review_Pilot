"""The PR Review Prep Agent, built on the Strands Agents SDK.

The model backend is selectable via the MODEL_BACKEND env var:
  - "bedrock" (default) -> Amazon Bedrock (the hackathon's recommended path)
  - "ollama"            -> a local Ollama model, for zero-cost development
"""

from __future__ import annotations

import os

from strands import Agent

from .tools import (
    get_pr_diff,
    get_pr_metadata,
    get_repo_conventions,
    post_review_comment,
)

SYSTEM_PROMPT = """\
You are a senior code reviewer preparing a human's review of a GitHub pull request.
You do NOT approve or merge. You gather context and produce review-prep material so
a human reviewer can act in minutes instead of an hour.

Your workflow for any PR:
1. Call get_pr_metadata to learn the title, author, size, and changed files.
2. Call get_pr_diff to read the actual changes.
3. Call get_repo_conventions to learn the repo's own rules, and hold the review to
   THOSE rules, not generic style opinions.

Then produce a single markdown report with these sections, in order:

## Summary
2-4 sentences: what this PR does and why, in plain language.

## Risk Flags
A bulleted list of the riskiest changes a reviewer must look at first. For each,
give the file and a one-line reason (e.g. auth logic, data migration, error handling
removed, secrets, breaking API change, missing tests). If there are none, say so.

## Convention Check
Concrete places the diff diverges from the repo's stated conventions, quoting the
convention. If no conventions file exists, say so and skip nitpicks.

## Review Checklist
5-8 specific, checkable questions tailored to THIS diff (not generic). Each should be
answerable by looking at a named file/change.

## Suggested PR Description
A clean, ready-to-paste PR description if the author's is thin or missing.

Rules:
- Be specific and cite file paths. Never invent files or lines not in the diff.
- Be concise. A reviewer should read your whole report in under two minutes.
- Never post anything yourself. Posting is a separate, human-approved step.
"""


def _build_model():
    backend = os.getenv("MODEL_BACKEND", "bedrock").lower()

    if backend == "ollama":
        from strands.models.ollama import OllamaModel

        return OllamaModel(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.getenv("OLLAMA_MODEL", "llama3.1"),
        )

    # Default: Amazon Bedrock. Uses standard AWS credential resolution
    # (env vars, ~/.aws/credentials, or an attached role).
    from strands.models import BedrockModel

    return BedrockModel(
        model_id=os.getenv(
            "BEDROCK_MODEL_ID",
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        ),
        region_name=os.getenv("AWS_REGION", "us-west-2"),
        temperature=0.2,
    )


def build_agent() -> Agent:
    """Construct the review-prep agent with its model, tools, and system prompt."""
    return Agent(
        model=_build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            get_pr_metadata,
            get_pr_diff,
            get_repo_conventions,
            post_review_comment,
        ],
    )

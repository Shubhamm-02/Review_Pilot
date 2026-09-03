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
You are Review Pilot, a senior code reviewer preparing a human's review of a GitHub
pull request. You do NOT approve or merge. You produce review-prep material so a human
reviewer can act in minutes instead of an hour.

You are given the full context for one pull request: its metadata, its diff, and the
repository's own conventions. Using ONLY that provided context, produce a single markdown
report with EXACTLY these five sections, each with its "##" heading, in this order
(never omit a section — if one is empty, say so under it):

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
            temperature=0.1,
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
    """Construct the review-prep agent with its model, tools, and system prompt.

    The three context-gathering tools remain registered so the agent can be driven
    autonomously on a strong backend (e.g. Bedrock/Claude), but the default
    prepare_review() flow gathers them deterministically for reliability on any model.
    """
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


def gather_context(pr_ref: str) -> str:
    """Deterministically fetch metadata, diff, and conventions and assemble one context blob.

    Doing this in code — rather than hoping the model calls all three tools — guarantees
    every review is built from the same complete context, on any model backend.
    """
    metadata = get_pr_metadata(pr_ref)
    diff = get_pr_diff(pr_ref)
    conventions = get_repo_conventions(pr_ref)
    return (
        f"Context for pull request {pr_ref}.\n\n"
        f"===== PR METADATA =====\n{metadata}\n\n"
        f"===== DIFF =====\n{diff}\n\n"
        f"===== REPOSITORY CONVENTIONS =====\n{conventions}\n"
    )


def prepare_review(pr_ref: str, agent: Agent | None = None) -> str:
    """Produce the full review briefing for a PR: gather context, then reason over it.

    Args:
        pr_ref: The pull request, as 'owner/repo#123' or a github.com pull URL.
        agent:  An optional pre-built agent (reused across calls); one is built if omitted.

    Returns:
        The five-section markdown review report.
    """
    agent = agent or build_agent()
    context = gather_context(pr_ref)
    instruction = (
        f"{context}\n"
        "Using ONLY the context above, write the review report now, with all five "
        "sections in order: ## Summary, ## Risk Flags, ## Convention Check, "
        "## Review Checklist, ## Suggested PR Description."
    )
    return str(agent(instruction))

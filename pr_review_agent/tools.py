"""Tools the agent uses to gather PR context from GitHub.

These wrap the authenticated `gh` CLI so the agent never needs raw tokens.
Each function is exposed to the Strands agent via the @tool decorator.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass

from strands import tool

# Conventions files we look for, in priority order.
_CONVENTION_FILES = [
    "CONTRIBUTING.md",
    ".github/CONTRIBUTING.md",
    "CONVENTIONS.md",
    "CLAUDE.md",
    "AGENTS.md",
    ".github/pull_request_template.md",
]

# Cap diff size so we never blow the model's context on a huge PR.
_MAX_DIFF_CHARS = 60_000


@dataclass
class PRRef:
    """A parsed reference to a pull request, e.g. 'owner/repo#123'."""

    owner: str
    repo: str
    number: int

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"


def parse_pr_ref(ref: str) -> PRRef:
    """Parse 'owner/repo#123' or a full PR URL into a PRRef."""
    ref = ref.strip()
    url_match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", ref)
    if url_match:
        owner, repo, num = url_match.groups()
        return PRRef(owner, repo, int(num))
    short_match = re.match(r"([^/]+)/([^/#]+)#(\d+)", ref)
    if short_match:
        owner, repo, num = short_match.groups()
        return PRRef(owner, repo, int(num))
    raise ValueError(
        f"Could not parse PR reference {ref!r}. "
        "Use 'owner/repo#123' or a full github.com pull URL."
    )


def _gh(args: list[str]) -> str:
    """Run a gh command and return stdout, raising a readable error on failure."""
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"`gh {' '.join(args)}` failed: {result.stderr.strip()}")
    return result.stdout


@tool
def get_pr_metadata(pr_ref: str) -> str:
    """Fetch title, author, description, and changed-file stats for a pull request.

    Args:
        pr_ref: The pull request, as 'owner/repo#123' or a github.com pull URL.

    Returns:
        A JSON string with the PR's title, author, body, state, and per-file
        addition/deletion counts.
    """
    pr = parse_pr_ref(pr_ref)
    raw = _gh(
        [
            "pr", "view", str(pr.number),
            "--repo", pr.slug,
            "--json", "title,author,body,state,additions,deletions,files,baseRefName,headRefName",
        ]
    )
    data = json.loads(raw)
    # Trim the file list to name + counts to keep the payload tight.
    data["files"] = [
        {"path": f["path"], "additions": f["additions"], "deletions": f["deletions"]}
        for f in data.get("files", [])
    ]
    data["author"] = data.get("author", {}).get("login", "unknown")
    return json.dumps(data, indent=2)


@tool
def get_pr_diff(pr_ref: str) -> str:
    """Fetch the unified diff (patch) for a pull request.

    Args:
        pr_ref: The pull request, as 'owner/repo#123' or a github.com pull URL.

    Returns:
        The unified diff as text. Very large diffs are truncated with a marker.
    """
    pr = parse_pr_ref(pr_ref)
    diff = _gh(["pr", "diff", str(pr.number), "--repo", pr.slug])
    if len(diff) > _MAX_DIFF_CHARS:
        diff = (
            diff[:_MAX_DIFF_CHARS]
            + "\n\n[... diff truncated: PR exceeds the size the agent reviews in one pass ...]"
        )
    return diff


@tool
def get_repo_conventions(pr_ref: str) -> str:
    """Fetch the repository's own contribution/style conventions, if any exist.

    Looks for CONTRIBUTING.md, CONVENTIONS.md, CLAUDE.md, AGENTS.md, and the
    PR template. The agent uses these so its review reflects the repo's actual
    rules rather than generic advice.

    Args:
        pr_ref: The pull request, as 'owner/repo#123' or a github.com pull URL.

    Returns:
        The text of the first conventions file found, or a note that none exist.
    """
    pr = parse_pr_ref(pr_ref)
    for path in _CONVENTION_FILES:
        try:
            content = _gh(
                ["api", f"repos/{pr.slug}/contents/{path}", "--jq", ".content"]
            )
        except RuntimeError:
            continue
        if content.strip():
            import base64

            try:
                decoded = base64.b64decode(content).decode("utf-8", errors="replace")
            except Exception:
                continue
            return f"# Conventions from {path}\n\n{decoded[:8000]}"
    return "No conventions file (CONTRIBUTING.md, CONVENTIONS.md, etc.) found in this repository."


@tool
def post_review_comment(pr_ref: str, body: str) -> str:
    """Post the prepared review as a comment on the pull request.

    This is gated behind explicit human approval in the CLI — the agent should
    only call it after the user confirms. Never call it automatically.

    Args:
        pr_ref: The pull request, as 'owner/repo#123' or a github.com pull URL.
        body: The markdown comment body to post.

    Returns:
        A confirmation string with the comment URL.
    """
    pr = parse_pr_ref(pr_ref)
    url = _gh(
        ["pr", "comment", str(pr.number), "--repo", pr.slug, "--body", body]
    )
    return f"Posted review comment: {url.strip()}"

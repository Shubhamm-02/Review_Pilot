"""CLI for the PR Review Prep Agent.

Usage:
    python main.py owner/repo#123
    python main.py https://github.com/owner/repo/pull/123
    python main.py owner/repo#123 --post   # offer to post the review after approval
"""

from __future__ import annotations

import argparse
import sys

from pr_review_agent.agent import build_agent, prepare_review
from pr_review_agent.tools import parse_pr_ref, post_review_comment


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a code review for a GitHub PR.")
    parser.add_argument("pr", help="PR reference: 'owner/repo#123' or a pull URL")
    parser.add_argument(
        "--post",
        action="store_true",
        help="After generating, ask for confirmation and post the review as a PR comment.",
    )
    args = parser.parse_args()

    # Validate the reference early so we fail fast with a clear message.
    try:
        parse_pr_ref(args.pr)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    agent = build_agent()

    print(f"Preparing review for {args.pr} ...\n", file=sys.stderr)
    report = prepare_review(args.pr, agent=agent)

    if args.post:
        print("\n" + "=" * 60, file=sys.stderr)
        answer = input("Post this report as a PR comment? [y/N] ").strip().lower()
        if answer == "y":
            # Call the tool directly — deterministic, no second model round-trip.
            confirmation = post_review_comment(pr_ref=args.pr, body=report)
            print(confirmation, file=sys.stderr)
        else:
            print("Not posted.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Review Pilot

**An AI agent that turns any GitHub pull request into a two-minute review.**
Built on the [Strands Agents SDK](https://strandsagents.com) for the *Agents for Humans* hackathon (Professional Agents track).

Every code review starts with the same repetitive busywork: read the whole diff, figure out
what actually changed, guess what's risky, and remember the repo's own conventions. **Review
Pilot** does that prep for you. Point it at a PR and it hands your human reviewer a
risk-flagged briefing — so a one-hour review becomes a two-minute one.

It **prepares**, it never approves or merges. A human stays in the loop for every decision.

---

## What it produces

For any pull request, the agent outputs a single markdown report:

- **Summary** — what the PR does and why, in plain language.
- **Risk Flags** — the riskiest changes to look at *first* (auth, migrations, removed error
  handling, secrets, breaking API changes, missing tests), each with a file and a one-line reason.
- **Convention Check** — where the diff diverges from *this repo's own* rules, read live from its
  `CONTRIBUTING.md` / `CONVENTIONS.md` / `CLAUDE.md`.
- **Review Checklist** — 5–8 specific, checkable questions tailored to this exact diff.
- **Suggested PR Description** — a clean, ready-to-paste description when the author's is thin.

Optionally, with `--post` and explicit human confirmation, it posts the report as a PR comment.

---

## How it works

Review Pilot has two stages. First it **deterministically gathers** the three context
sources every review needs, so no review is ever missing context. Then the **Strands agent
reasons** over that context to produce the briefing. A human approves any write action.

| Tool | What it does |
|------|--------------|
| `get_pr_metadata` | Title, author, description, size, changed-file stats |
| `get_pr_diff` | The unified diff (truncated safely on huge PRs) |
| `get_repo_conventions` | The repo's own contribution/style rules |
| `post_review_comment` | Posts the review — **human-gated, never automatic** |

The first three run up front in `gather_context()`; the agent then reasons over the result.
All four remain registered as Strands tools, so on a strong backend (Bedrock/Claude) the
agent can also be driven fully autonomously. All GitHub access goes through the authenticated
`gh` CLI, so the agent never handles raw tokens.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full diagram.

---

## Quick start

Requires Python 3.10+, the [`gh` CLI](https://cli.github.com) (authenticated: `gh auth login`),
and a model backend (Amazon Bedrock, or Ollama for local dev).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Choose a backend
cp .env.example .env        # then edit, or export the vars below

# Run it
python main.py owner/repo#123
python main.py https://github.com/owner/repo/pull/123 --post
```

### Model backends

The backend is selected by the `MODEL_BACKEND` env var — no code changes needed.

**Amazon Bedrock (recommended, hackathon path):**
```bash
export MODEL_BACKEND=bedrock
export AWS_REGION=us-west-2
export BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
# plus standard AWS credentials (env vars or ~/.aws/credentials)
```

**Ollama (free local development):**
```bash
export MODEL_BACKEND=ollama
export OLLAMA_MODEL=qwen2.5:7b      # a tool-calling-capable model
```

---

## Deployment

For the hackathon submission, Review Pilot deploys to **Amazon Bedrock AgentCore Runtime**.
See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the deployment path.

---

## License

Apache License 2.0 — see [`LICENSE`](./LICENSE).
